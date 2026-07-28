"""Sunnify headless CLI - the GUI's engine with a terminal face.

Same matcher, same naming, same tag writer, same config file as the desktop
app: the CLI constructs the GUI's own MusicScraper and drives it without a
QApplication, so behavior can never drift between the two.

Design contract (stable for scripts and AI agents):
- subcommands: download, info, status, config, doctor
- `--json` emits NDJSON events on stdout for download, one JSON document for
  the others (schema in docs/CLI.md); human output otherwise
- exit codes: 0 success, 1 some tracks failed/stopped, 2 usage error,
  3 environment/fatal error
- never interactive: no prompts, sane defaults, everything overridable
- defaults come from the GUI's saved settings (config.json), flags override
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import signal
import sys
import threading
import time

import Spotify_Downloader as app
from spotifydown_api import PlaylistClient, SpotifyEmbedAPI

EXIT_OK = 0
EXIT_PARTIAL = 1
EXIT_USAGE = 2  # argparse's own code for bad usage
EXIT_FATAL = 3

_LOCK_NAME = ".sunnify-cli.lock"


def _ensure_windows_console() -> None:
    """Attach to the parent console when the windowed exe runs interactively.

    Piped/redirected stdio (how agents and scripts call us) already works in
    a windowed build; this covers a human typing in cmd/powershell, where a
    /SUBSYSTEM:WINDOWED exe has no console by default.
    ref: https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html
    """
    if sys.platform != "win32":
        return
    try:
        broken = sys.stdout is None or sys.stdout.fileno() < 0
    except (AttributeError, OSError, ValueError):
        broken = True
    if not broken:
        return
    import ctypes

    if ctypes.windll.kernel32.AttachConsole(-1):  # ATTACH_PARENT_PROCESS
        sys.stdout = open("CONOUT$", "w", buffering=1, encoding="utf-8")  # noqa: SIM115
        sys.stderr = open("CONOUT$", "w", buffering=1, encoding="utf-8")  # noqa: SIM115
    else:
        # no console anywhere: keep streams valid so prints never crash
        sys.stdout = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
        sys.stderr = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115


class _Emitter:
    """Thread-safe progress output: human lines or NDJSON events."""

    def __init__(self, as_json: bool, quiet: bool = False):
        self.as_json = as_json
        self.quiet = quiet
        self._lock = threading.Lock()

    def event(self, name: str, **fields) -> None:
        with self._lock:
            if self.as_json:
                print(json.dumps({"event": name, **fields}, ensure_ascii=False), flush=True)
            elif not self.quiet:
                self._human(name, fields)

    def error(self, message: str, code: str = "error", hint: str | None = None) -> None:
        """Typed error envelope: agents branch on `code`, humans read the hint."""
        if self.as_json:
            self.event("error", code=code, message=message, hint=hint)
        else:
            print(f"error: {message}", file=sys.stderr, flush=True)
            if hint:
                print(f"  hint: {hint}", file=sys.stderr, flush=True)

    def _human(self, name: str, f: dict) -> None:
        if name == "run_started":
            print(f"» {f['url']}  ->  {f['folder']}  [{f['format']}]", flush=True)
        elif name == "track_done":
            print(f"  ✓ {os.path.basename(f['file'])}", flush=True)
        elif name == "track_skipped":
            print(f"  = {os.path.basename(f['file'])} (already on disk)", flush=True)
        elif name == "warning":
            print(f"  ! {f['message']}", flush=True)
        elif name == "run_summary":
            print(
                f"done: {f['landed']} landed, {f['skipped']} already present, "
                f"{f['failed']} failed in {f['elapsed_s']}s -> {f['folder']}",
                flush=True,
            )


def _resolve_out_dir(out_arg: str | None, cfg: dict) -> str:
    out = (
        out_arg
        or cfg.get("download_path")
        or os.path.join(os.path.expanduser("~"), "Music", "Sunnify")
    )
    return os.path.abspath(os.path.expanduser(out))


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes

        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _read_lock_pid(folder: str) -> int | None:
    with contextlib.suppress(OSError, ValueError):
        with open(os.path.join(folder, _LOCK_NAME), encoding="utf-8") as fh:
            pid = int(fh.read().strip())
        if _pid_alive(pid):
            return pid
    return None


class _FolderLock:
    """Pid lockfile so two CLI runs can't race the same folder; stale locks
    (dead pid) are claimed silently."""

    def __init__(self, folder: str):
        self.path = os.path.join(folder, _LOCK_NAME)
        self.folder = folder

    def acquire(self) -> str | None:
        """Return an error message, or None once the lock is held."""
        pid = _read_lock_pid(self.folder)
        if pid is not None and pid != os.getpid():
            return f"another sunnify download (pid {pid}) is writing to this folder"
        with contextlib.suppress(OSError), open(self.path, "w", encoding="utf-8") as fh:
            fh.write(str(os.getpid()))
        return None

    def release(self) -> None:
        with contextlib.suppress(OSError):
            os.remove(self.path)


class _RunState:
    """Collects per-track outcomes from the scraper's signals.

    song_meta fires before the exists-check result is acted on, so the
    pre-existing test here (before download starts) cleanly separates
    "skipped, was already on disk" from "landed this run".
    """

    def __init__(self, emitter: _Emitter):
        self.emitter = emitter
        self.landed: list[str] = []
        self.skipped: list[str] = []
        self.resume_skipped = 0
        self._preexisting: set[str] = set()
        self._lock = threading.Lock()

    def on_resume_skipped(self, count: int) -> None:
        self.resume_skipped = int(count)

    def on_song_meta(self, meta: dict) -> None:
        path = meta.get("file", "")
        if path and os.path.exists(path):
            with self._lock:
                self._preexisting.add(path)

    def on_add_song_meta(self, meta: dict) -> None:
        path = meta.get("file", "")
        with self._lock:
            pre = path in self._preexisting
        if pre:
            self.skipped.append(path)
            self.emitter.event("track_skipped", title=meta.get("title", ""), file=path)
            return
        # same tag writer the GUI uses, run synchronously (no thread started)
        app.WritingMetaTagsThread(meta, path).run()
        if os.path.exists(path):
            self.landed.append(path)
            self.emitter.event(
                "track_done",
                title=meta.get("title", ""),
                artists=meta.get("artists", ""),
                file=path,
                bytes=os.path.getsize(path),
            )

    def on_error(self, message: str) -> None:
        self.emitter.event("warning", message=str(message))


def _resolve_settings(args, cfg: dict) -> dict:
    """flags > saved config > defaults, driven entirely by the registry."""
    resolved = dict(cfg)
    for s in app.SETTINGS:
        if s.cli_flag is None:
            continue
        flag_value = getattr(args, s.cli_flag.lstrip("-").replace("-", "_"), None)
        if flag_value is not None:
            resolved[s.key] = flag_value
    return resolved


def _build_scraper(args, cfg: dict, cancel_event: threading.Event) -> app.MusicScraper:
    return app.MusicScraper(
        cancel_event=cancel_event, **app.scraper_kwargs_from(_resolve_settings(args, cfg))
    )


def cmd_download(args) -> int:
    cfg = app.load_config()
    out_dir = _resolve_out_dir(args.out, cfg)
    emitter = _Emitter(args.json, args.quiet)

    try:
        url_type, item_id = app.detect_spotify_url_type(args.url)
    except ValueError:
        url_type, item_id = "unknown", None
    if url_type == "unknown" or not item_id:
        emitter.error(
            f"not a spotify playlist/album/track url: {args.url}",
            code="invalid_url",
            hint="expected https://open.spotify.com/{playlist,album,track}/... or a spotify: uri",
        )
        return EXIT_FATAL
    try:
        os.makedirs(out_dir, exist_ok=True)
    except OSError as exc:
        emitter.error(
            f"cannot create output folder {out_dir}: {exc}",
            code="out_dir_unusable",
            hint="pass a writable folder with --out",
        )
        return EXIT_FATAL
    if not os.access(out_dir, os.W_OK):
        emitter.error(
            f"output folder is not writable: {out_dir}",
            code="out_dir_unusable",
            hint="pass a writable folder with --out",
        )
        return EXIT_FATAL
    if app.get_ffmpeg_path() is None:
        emitter.error(
            "ffmpeg not found",
            code="ffmpeg_missing",
            hint=(
                "the prebuilt sunnify binaries bundle ffmpeg; source installs need it on PATH "
                "(brew install ffmpeg / apt install ffmpeg / winget install ffmpeg)"
            ),
        )
        return EXIT_FATAL

    lock = _FolderLock(out_dir)
    lock_err = lock.acquire()
    if lock_err:
        emitter.error(
            lock_err,
            code="folder_locked",
            hint="wait for the other run to finish, or pass a different --out",
        )
        return EXIT_FATAL

    cancel_event = threading.Event()
    scraper = _build_scraper(args, cfg, cancel_event)
    state = _RunState(emitter)
    # workers emit from pool threads; with no qt event loop running, queued
    # (auto) connections are never delivered, so force direct delivery
    from PyQt6.QtCore import Qt

    direct = Qt.ConnectionType.DirectConnection
    scraper.song_meta.connect(state.on_song_meta, type=direct)
    scraper.add_song_meta.connect(state.on_add_song_meta, type=direct)
    scraper.resume_skipped.connect(state.on_resume_skipped, type=direct)
    scraper.error_signal.connect(state.on_error, type=direct)

    # graceful ^C: first stops after in-flight tracks, second is immediate
    def _sigint(_sig, _frame):
        if cancel_event.is_set():
            lock.release()
            os._exit(130)
        cancel_event.set()
        emitter.error("stopping after in-flight tracks finish (^C again to force quit)")

    with contextlib.suppress(Exception):
        signal.signal(signal.SIGINT, _sigint)

    emitter.event(
        "run_started",
        url=args.url,
        type=url_type,
        folder=out_dir,
        format=scraper.audio_format,
        quality=scraper.audio_quality,
        sample_rate=scraper.sample_rate,
        artist_first=scraper.artist_first,
        track_numbers=scraper.include_track_number,
        loose_match=scraper.loose_match,
    )
    t0 = time.monotonic()
    try:
        if url_type == "track":
            scraper.scrape_track(args.url, out_dir)
        else:
            scraper.scrape_playlist(args.url, out_dir)
    except Exception as exc:
        emitter.error(f"download run failed: {exc}", code="run_failed", hint="run `sunnify doctor`")
        return EXIT_FATAL
    finally:
        lock.release()

    failed = list(scraper._failed_tracks)
    stopped = cancel_event.is_set()
    code = EXIT_PARTIAL if (failed or stopped) else EXIT_OK
    emitter.event(
        "run_summary",
        landed=len(state.landed),
        skipped=len(state.skipped) + state.resume_skipped,
        failed=len(failed),
        failed_titles=failed,
        stopped=stopped,
        elapsed_s=round(time.monotonic() - t0, 1),
        folder=out_dir,
        exit_code=code,
    )
    if failed and not args.json:
        for title in failed:
            print(f"  failed: {title}", file=sys.stderr)
    return code


def cmd_info(args) -> int:
    emitter = _Emitter(args.json)
    try:
        url_type, item_id = app.detect_spotify_url_type(args.url)
    except ValueError:
        url_type, item_id = "unknown", None
    if url_type == "unknown" or not item_id:
        emitter.error(
            f"not a spotify playlist/album/track url: {args.url}",
            code="invalid_url",
            hint="expected https://open.spotify.com/{playlist,album,track}/... or a spotify: uri",
        )
        return EXIT_FATAL
    try:
        if url_type == "track":
            track = SpotifyEmbedAPI().get_track(item_id)
            payload = {
                "type": "track",
                "id": track.spotify_id,
                "title": track.title,
                "artists": track.artists,
                "album": track.album or "",
                "release_date": track.release_date or "",
                "duration_ms": track.duration_ms or 0,
            }
        else:
            client = PlaylistClient()
            meta = client.get_playlist_metadata(item_id, content_type=url_type)
            tracks = [
                {
                    "id": t.spotify_id,
                    "title": t.title,
                    "artists": t.artists,
                    "duration_ms": t.duration_ms or 0,
                }
                for t in client.iter_playlist_tracks(item_id, content_type=url_type)
            ]
            payload = {
                "type": url_type,
                "id": item_id,
                "name": meta.name,
                "owner": meta.owner or "",
                "track_count": len(tracks),
                "tracks": tracks,
            }
    except Exception as exc:
        emitter.error(
            f"could not fetch metadata: {exc}",
            code="metadata_fetch_failed",
            hint="check the url is public and reachable; `sunnify doctor` tests upstream health",
        )
        return EXIT_FATAL

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif payload["type"] == "track":
        print(f"{payload['title']} - {payload['artists']}  [track]")
    else:
        print(f"{payload['name']}  [{payload['type']}, {payload['track_count']} tracks]")
        for t in payload["tracks"]:
            print(f"  {t['title']} - {t['artists']}")
    return EXIT_OK


def cmd_status(args) -> int:
    cfg = app.load_config()
    folder = os.path.abspath(os.path.expanduser(args.folder or _resolve_out_dir(None, cfg)))
    manifest = os.path.join(folder, app.MANIFEST_FILENAME)
    entries: list[dict] = []
    if os.path.exists(manifest):
        with contextlib.suppress(OSError), open(manifest, encoding="utf-8") as fh:
            for line in fh:
                with contextlib.suppress(ValueError):
                    entries.append(json.loads(line))
    # manifest records store basenames relative to their folder; single-track
    # downloads never write a manifest, so count real audio files too
    on_disk = [e for e in entries if os.path.exists(os.path.join(folder, e.get("file", "")))]
    missing = [e for e in entries if e not in on_disk]
    exts = tuple(f".{spec['ext']}" for spec in app.SUPPORTED_FORMATS.values())
    audio_files: list[str] = []
    with contextlib.suppress(OSError):
        audio_files = sorted(n for n in os.listdir(folder) if n.lower().endswith(exts))
    active_pid = _read_lock_pid(folder)
    payload = {
        "folder": folder,
        "audio_files": len(audio_files),
        "manifest_entries": len(entries),
        "recorded_but_missing": len(missing),
        "download_in_progress": active_pid is not None,
        "active_pid": active_pid,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        state = f"downloading now (pid {active_pid})" if active_pid else "idle"
        print(
            f"{folder}: {len(audio_files)} audio files, {len(missing)} recorded but missing, {state}"
        )
    return EXIT_OK


def cmd_config(args) -> int:
    cfg = app.load_config()
    registry = {s.key: s for s in app.SETTINGS}
    if args.set:
        for pair in args.set:
            key, sep, value = pair.partition("=")
            setting = registry.get(key)
            if not sep or setting is None:
                print(
                    f"error: --set expects key=value with a known key "
                    f"(valid: {', '.join(sorted(registry))}), got {pair!r}",
                    file=sys.stderr,
                )
                return EXIT_USAGE
            if setting.kind == "bool":
                if value.lower() not in ("true", "false"):
                    print(f"error: {key} must be true or false", file=sys.stderr)
                    return EXIT_USAGE
                cfg[key] = value.lower() == "true"
            elif setting.kind == "choice":
                if value not in setting.choices:
                    print(
                        f"error: {key} must be one of: {', '.join(setting.choices)}",
                        file=sys.stderr,
                    )
                    return EXIT_USAGE
                cfg[key] = value
            else:
                cfg[key] = value
        app.save_config(cfg)
    visible = {k: v for k, v in cfg.items() if k not in ("version", "star_prompt_shown")}
    if args.json:
        print(json.dumps(visible, ensure_ascii=False, indent=2))
    else:
        for key in sorted(visible):
            print(f"{key} = {visible[key]}")
    return EXIT_OK


def cmd_doctor(args) -> int:
    """Environment self-check: the command to run when downloads misbehave."""
    checks: list[dict] = []

    ffmpeg = app.get_ffmpeg_path()
    checks.append(
        {
            "check": "ffmpeg",
            "ok": ffmpeg is not None,
            "detail": ffmpeg
            or "not found (bundled in prebuilt binaries; else install via brew/apt/winget)",
        }
    )

    cfg_ok, cfg_detail = True, app._config_path()
    try:
        app.load_config()
    except Exception as exc:  # load_config swallows almost everything; belt and braces
        cfg_ok, cfg_detail = False, str(exc)
    checks.append({"check": "config", "ok": cfg_ok, "detail": cfg_detail})
    checks.append({"check": "logs", "ok": True, "detail": app._log_dir()})

    try:
        SpotifyEmbedAPI().get_track("4uLU6hMCjMI75M1A2tKUQC")  # never gonna give you up
        checks.append(
            {"check": "spotify_metadata", "ok": True, "detail": "embed endpoint reachable"}
        )
    except Exception as exc:
        checks.append({"check": "spotify_metadata", "ok": False, "detail": str(exc)})

    try:
        import yt_dlp

        checks.append(
            {"check": "yt_dlp", "ok": True, "detail": f"version {yt_dlp.version.__version__}"}
        )
    except Exception as exc:
        checks.append({"check": "yt_dlp", "ok": False, "detail": str(exc)})

    # ok stays True either way: being behind is a nudge, not an unhealthy env
    try:
        r = app.requests.get(
            app._LATEST_RELEASE_API, timeout=5, headers={"Accept": "application/vnd.github+json"}
        )
        tag = (r.json().get("tag_name") or "").lstrip("vV") if r.status_code == 200 else ""
        if tag and app._is_newer_version(tag, app.__version__):
            detail = f"{app.__version__} installed, {tag} available: {app._RELEASES_PAGE}"
        elif tag:
            detail = f"{app.__version__} is the latest release"
        elif r.status_code in (403, 429):
            # unauthenticated github rest is 60 req/hour/ip; never worth failing over
            detail = f"{app.__version__} (release check rate-limited by github, try later)"
        else:
            detail = f"{app.__version__} (release check got http {r.status_code})"
    except Exception as exc:
        detail = f"{app.__version__} (release check unreachable: {exc})"
    checks.append({"check": "version", "ok": True, "detail": detail})

    all_ok = all(c["ok"] for c in checks)
    if args.json:
        print(json.dumps({"ok": all_ok, "checks": checks}, ensure_ascii=False, indent=2))
    else:
        for c in checks:
            print(f"  {'✓' if c['ok'] else '✗'} {c['check']}: {c['detail']}")
        print("all good" if all_ok else "problems found - fix the ✗ lines above")
    return EXIT_OK if all_ok else EXIT_FATAL


def build_parser() -> argparse.ArgumentParser:
    cfg = app.load_config()
    parser = argparse.ArgumentParser(
        prog="sunnify",
        description=(
            "Sunnify headless CLI: download Spotify playlists, albums, and tracks "
            "as tagged local audio files. Same engine and settings as the desktop app."
        ),
        epilog=(
            "examples:\n"
            '  sunnify download "https://open.spotify.com/playlist/..."\n'
            '  sunnify download "https://open.spotify.com/track/..." -o ~/Music -f flac --sample-rate 44100\n'
            '  sunnify download "<url>" --json           # NDJSON progress events for scripts/agents\n'
            '  sunnify info "<url>" --json               # metadata only, no download\n'
            "  sunnify status                            # what's landed in the download folder\n"
            "  sunnify config --set format=m4a           # persist a setting (shared with the GUI)\n"
            "  sunnify doctor                            # self-check when downloads misbehave\n"
            "\nfull reference: https://github.com/sunnypatell/sunnify-spotify-downloader/blob/main/docs/CLI.md"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", "-V", action="version", version=f"sunnify {app.__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="command")

    dl = sub.add_parser(
        "download",
        help="download a playlist, album, or track",
        description=(
            "Download every track of a Spotify playlist/album, or a single track. "
            "Tracks already in the folder are skipped, so re-running resumes automatically."
        ),
    )
    dl.add_argument("url", help="spotify playlist/album/track url (or spotify: uri)")
    dl.add_argument(
        "--out",
        "-o",
        default=None,
        help=f"output folder (default: {cfg.get('download_path') or '~/Music/Sunnify'})",
    )
    # every scraper setting becomes a flag straight from the registry, so a
    # new app setting reaches the CLI with no changes here
    short = {"--format": "-f", "--quality": "-q"}
    for s in app.SETTINGS:
        if s.cli_flag is None:
            continue
        names = [s.cli_flag] + ([short[s.cli_flag]] if s.cli_flag in short else [])
        if s.kind == "bool":
            dl.add_argument(
                *names,
                action=argparse.BooleanOptionalAction,
                default=None,
                help=f"{s.help} (default: {cfg[s.key]})",
            )
        else:
            dl.add_argument(
                *names,
                choices=s.choices,
                default=None,
                help=f"{s.help} (default: {cfg[s.key]}, from saved settings)",
            )
    dl.add_argument("--json", action="store_true", help="emit NDJSON progress events on stdout")
    dl.add_argument(
        "--quiet", "-Q", action="store_true", help="suppress progress (errors still print)"
    )
    dl.set_defaults(func=cmd_download)

    info = sub.add_parser(
        "info",
        help="fetch metadata without downloading",
        description="Print playlist/album/track metadata. No downloads, no ffmpeg needed.",
    )
    info.add_argument("url", help="spotify playlist/album/track url")
    info.add_argument("--json", action="store_true", help="emit one JSON document")
    info.set_defaults(func=cmd_info)

    status = sub.add_parser(
        "status",
        help="show what a download folder contains",
        description=(
            "Read the resume manifest in a folder: tracks on disk, recorded-but-missing, "
            "and whether a CLI download is writing there right now."
        ),
    )
    status.add_argument(
        "folder",
        nargs="?",
        default=None,
        help="folder to inspect (default: the configured download folder)",
    )
    status.add_argument("--json", action="store_true", help="emit one JSON document")
    status.set_defaults(func=cmd_status)

    config = sub.add_parser(
        "config",
        help="show or change saved settings (shared with the GUI)",
        description="Print the effective settings, or persist changes with --set.",
    )
    config.add_argument(
        "--set",
        action="append",
        metavar="key=value",
        help="persist a setting (repeatable), e.g. --set format=flac --set artist_first=true",
    )
    config.add_argument("--json", action="store_true", help="emit one JSON document")
    config.set_defaults(func=cmd_config)

    doctor = sub.add_parser(
        "doctor",
        help="check ffmpeg, config, and upstream reachability",
        description="Self-check the environment; run this first when downloads misbehave.",
    )
    doctor.add_argument("--json", action="store_true", help="emit one JSON document")
    doctor.set_defaults(func=cmd_doctor)

    return parser


def _forensic_sigterm(sig, _frame):
    """Same signal forensics as the app: name the killer, then die normally."""
    import logging

    with contextlib.suppress(Exception):
        app.log.info("terminated by signal %s (cli)", signal.Signals(sig).name)
        logging.shutdown()
    signal.signal(sig, signal.SIG_DFL)
    os.kill(os.getpid(), sig)


def main(argv: list[str] | None = None) -> int:
    _ensure_windows_console()
    # same rotating session log as the GUI; never a reason to fail a run
    with contextlib.suppress(Exception):
        app.setup_logging()
        app.log.info("cli invoked: %s", " ".join(argv or sys.argv[1:]))
    with contextlib.suppress(Exception):
        signal.signal(signal.SIGTERM, _forensic_sigterm)
    if argv is None:
        argv = sys.argv[1:]
    # git-style `help [command]` alias
    if argv[:1] == ["help"]:
        argv = [argv[1], "--help"] if len(argv) > 1 else ["--help"]
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        rc = args.func(args)
    except KeyboardInterrupt:
        rc = 130
    with contextlib.suppress(Exception):
        app.log.info("cli exit: code=%d", rc)
    return rc


if __name__ == "__main__":
    sys.exit(main())
