#
"""
Sunnify (Spotify Downloader)
Copyright (C) 2024-2026 Sunny Patel <sunnypatel124555@gmail.com>

EDUCATIONAL PROJECT DISCLAIMER:
This software is a student portfolio project developed for educational purposes only.
It is intended to demonstrate software engineering skills and is provided free of charge.
Users are solely responsible for ensuring compliance with applicable laws in their jurisdiction.
This software should only be used with content you own or have permission to download.
See DISCLAIMER.md for full terms.

The program's entry point: `python Spotify_Downloader.py` opens the desktop app,
and `python Spotify_Downloader.py <command>` runs the headless CLI. The packaged
binaries are built from this file too.

The code lives in the `sunnify` package (see sunnify/__init__.py for the map).
`import Spotify_Downloader` still works and still exposes every name it used to,
loaded on first use, so scripts written against the old single-file layout keep
running. Names are read-only here: patch them where they are defined
(sunnify.tools.get_ffmpeg_path, not Spotify_Downloader.get_ffmpeg_path), because
a patch on this facade would never reach the code that calls them.
"""

from __future__ import annotations

import importlib
import sys
import types

from sunnify import __version__  # noqa: F401  (the version every surface reports)

# name -> defining module, for the names the single-file layout exposed
_EXPORTS = {
    "sunnify.logs": (
        "log _log_excepthook _thread_excepthook _install_crash_handlers _log_dir "
        "log_file_path setup_logging"
    ),
    "sunnify.tools": (
        "get_ffmpeg_path ffmpeg_install_hint _JS_RUNTIMES _js_runtime_candidates "
        "find_js_runtime _read_cookie_jar _cookies_text cookies_problem"
    ),
    "sunnify.config": (
        "SUPPORTED_FORMATS SUPPORTED_QUALITIES SUPPORTED_SAMPLE_RATES SUPPORTED_UI_SCALES "
        "SUPPORTED_LANGUAGES SUPPORTED_THEMES UI_STATE_DEFAULTS _Setting SETTINGS "
        "scraper_kwargs_from _config_dir _config_path load_config save_config"
    ),
    "sunnify.locking": (
        "LOCK_FILENAME FolderLockedError _pid_alive _lock_file_pid read_lock_pid folder_lock"
    ),
    "sunnify.updates": (
        "GITHUB_REPO _LATEST_RELEASE_API _RELEASES_PAGE _parse_version _is_newer_version "
        "_check_for_update UpdateCheckThread"
    ),
    "sunnify.tagging": (
        "_fetch_cover_bytes _detect_image_mime _write_metadata_mp3 _write_metadata_m4a "
        "_write_metadata_flac WritingMetaTagsThread"
    ),
    "sunnify.engine": (
        "MANIFEST_FILENAME _YtdlpLog _RETRY_CLIENTS _retry_player_clients MusicScraper "
        "ScraperThread"
    ),
    "sunnify.gui.scale": (
        "WINDOW_W WINDOW_H apply_ui_scale _current_ui_factor _relaunch_command relaunch_app "
        "_ui_scale_env_is_ours"
    ),
    "sunnify.gui.dialogs": "SettingsDialog UpdateNotifier StarPromptNotifier HistoryDialog",
    "sunnify.gui.window": "MainWindow DownloadThumbnail",
}
_WHERE = {name: module for module, names in _EXPORTS.items() for name in names.split()}


def __getattr__(name: str):
    """Resolve on every access, so mutable module state (a flag) is never a stale copy."""
    module = _WHERE.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(importlib.import_module(module), name)


def __dir__():
    return sorted(set(globals()) | set(_WHERE))


class _ReadOnlyFacade(types.ModuleType):
    @staticmethod
    def _refuse(name):
        raise AttributeError(
            f"Spotify_Downloader.{name} is a re-export; patch {_WHERE[name]}.{name} instead"
        )

    def __setattr__(self, name, value):
        if name in _WHERE:
            self._refuse(name)
        super().__setattr__(name, value)

    # mock.patch deletes on the way out of a failed patch; say the same thing there
    def __delattr__(self, name):
        if name in _WHERE:
            self._refuse(name)
        super().__delattr__(name)


CLI_COMMANDS = ("download", "info", "status", "history", "config", "doctor", "help")


def main(argv: list[str] | None = None) -> int:
    """GUI by default; a known first word (or --version/--help) is the headless CLI."""
    argv = sys.argv[1:] if argv is None else argv
    arg1 = argv[0] if argv else ""
    if arg1 in CLI_COMMANDS or arg1 in ("--version", "-V", "--help", "-h"):
        import sunnify_cli

        return sunnify_cli.main(argv)
    if arg1.isascii() and arg1.isalpha():
        # a bare word is a command attempt, not launcher argv (macOS -psn_*,
        # file paths all carry non-letters); don't swallow it into a GUI launch
        import difflib

        close = difflib.get_close_matches(arg1.lower(), CLI_COMMANDS, n=1)
        hint = f" (did you mean '{close[0]}'?)" if close else ""
        print(
            f"sunnify: unknown command '{arg1}'{hint}\nrun 'sunnify --help' for usage",
            file=sys.stderr,
        )
        return 2
    from sunnify.gui.app import run

    return run()


if __name__ == "__main__":
    sys.exit(main())
else:
    sys.modules[__name__].__class__ = _ReadOnlyFacade
