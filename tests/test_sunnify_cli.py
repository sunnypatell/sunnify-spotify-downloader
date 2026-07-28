"""Tests for the headless CLI (sunnify_cli).

No network, no downloads: command surface, settings registry parity,
config round-trips, error envelopes, and the folder lock. The real
download path is the GUI's own MusicScraper, covered by its own tests.
"""

from __future__ import annotations

import inspect
import json
import os
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import Spotify_Downloader as sd
import sunnify_cli as cli

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _args(**kw):
    """Namespace with every download flag defaulted to None (not passed)."""
    base = {"url": "", "out": None, "json": False, "quiet": True}
    for s in sd.SETTINGS:
        if s.cli_flag:
            base[s.cli_flag.lstrip("-").replace("-", "_")] = None
    base.update(kw)
    return SimpleNamespace(**base)


class TestRegistryParity:
    """The single-source-of-truth guarantees: a new setting added to
    SETTINGS reaches config io, the scraper, and the CLI with no manual
    parity work - these tests fail loudly if that contract breaks."""

    def test_every_scraper_kwarg_is_a_real_ctor_param(self):
        params = inspect.signature(sd.MusicScraper.__init__).parameters
        for s in sd.SETTINGS:
            if s.scraper_kwarg:
                assert s.scraper_kwarg in params, f"{s.key} maps to unknown kwarg {s.scraper_kwarg}"

    def test_every_cli_flag_appears_in_download_help(self):
        help_text = (
            cli.build_parser()._subparsers._group_actions[0].choices["download"].format_help()
        )
        for s in sd.SETTINGS:
            if s.cli_flag:
                assert s.cli_flag in help_text, f"{s.cli_flag} missing from download --help"

    def test_load_config_keys_match_registry(self):
        cfg = sd.load_config()
        expected = {s.key for s in sd.SETTINGS} | {"version", "star_prompt_shown"}
        assert set(cfg) == expected

    def test_scraper_kwargs_from_covers_all_wired_settings(self):
        kwargs = sd.scraper_kwargs_from({s.key: s.default for s in sd.SETTINGS})
        assert set(kwargs) == {s.scraper_kwarg for s in sd.SETTINGS if s.scraper_kwarg}


class TestResolveSettings:
    def test_flag_overrides_saved_config(self):
        cfg = {s.key: s.default for s in sd.SETTINGS}
        cfg["format"] = "m4a"
        resolved = cli._resolve_settings(_args(format="flac"), cfg)
        assert resolved["format"] == "flac"

    def test_unset_flag_falls_through_to_config(self):
        cfg = {s.key: s.default for s in sd.SETTINGS}
        cfg["artist_first"] = True
        resolved = cli._resolve_settings(_args(), cfg)
        assert resolved["artist_first"] is True


class TestEmitter:
    def test_ndjson_events_are_parseable_lines(self, capsys):
        em = cli._Emitter(as_json=True)
        em.event("run_started", url="u", folder="f", format="mp3")
        em.event(
            "run_summary", landed=1, skipped=0, failed=0, elapsed_s=1.0, folder="f", exit_code=0
        )
        lines = capsys.readouterr().out.strip().splitlines()
        parsed = [json.loads(line) for line in lines]
        assert [p["event"] for p in parsed] == ["run_started", "run_summary"]

    def test_error_envelope_carries_code_and_hint(self, capsys):
        em = cli._Emitter(as_json=True)
        em.error("boom", code="ffmpeg_missing", hint="install it")
        parsed = json.loads(capsys.readouterr().out.strip())
        assert parsed == {
            "event": "error",
            "code": "ffmpeg_missing",
            "message": "boom",
            "hint": "install it",
        }

    def test_quiet_suppresses_human_progress_not_errors(self, capsys):
        em = cli._Emitter(as_json=False, quiet=True)
        em.event("track_done", file="x.mp3")
        em.error("kept", hint=None)
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "kept" in captured.err


class TestDownloadGuards:
    """Fatal-path guards return typed envelopes without touching the network."""

    def test_invalid_url_is_fatal_with_code(self, capsys):
        rc = cli.cmd_download(_args(url="https://example.com/nope", json=True))
        assert rc == cli.EXIT_FATAL
        assert json.loads(capsys.readouterr().out)["code"] == "invalid_url"

    def test_missing_ffmpeg_is_fatal_with_code(self, tmp_path, capsys):
        with patch.object(sd, "get_ffmpeg_path", return_value=None):
            rc = cli.cmd_download(
                _args(
                    url="https://open.spotify.com/track/0VjIjW4GlUZAMYd2vXMi3b",
                    out=str(tmp_path),
                    json=True,
                )
            )
        assert rc == cli.EXIT_FATAL
        assert json.loads(capsys.readouterr().out)["code"] == "ffmpeg_missing"

    def test_locked_folder_is_fatal_with_code(self, tmp_path, capsys):
        # pid 1 is alive and is not us on any posix system; windows CI skips
        if sys.platform == "win32":
            pytest.skip("posix pid semantics")
        (tmp_path / cli._LOCK_NAME).write_text("1")
        with patch.object(sd, "get_ffmpeg_path", return_value="/usr/bin/true"):
            rc = cli.cmd_download(
                _args(
                    url="https://open.spotify.com/track/0VjIjW4GlUZAMYd2vXMi3b",
                    out=str(tmp_path),
                    json=True,
                )
            )
        assert rc == cli.EXIT_FATAL
        assert json.loads(capsys.readouterr().out)["code"] == "folder_locked"


class TestFolderLock:
    def test_stale_lock_is_claimed(self, tmp_path):
        (tmp_path / cli._LOCK_NAME).write_text("999999999")
        lock = cli._FolderLock(str(tmp_path))
        assert lock.acquire() is None
        assert (tmp_path / cli._LOCK_NAME).read_text() == str(os.getpid())
        lock.release()
        assert not (tmp_path / cli._LOCK_NAME).exists()


class TestConfigCommand:
    def _run(self, tmp_path, *set_pairs, as_json=False):
        cfg_file = tmp_path / "config.json"
        with patch.object(sd, "_config_path", return_value=str(cfg_file)):
            args = SimpleNamespace(set=list(set_pairs) or None, json=as_json)
            rc = cli.cmd_config(args)
        return rc, cfg_file

    def test_set_persists_and_validates(self, tmp_path, capsys):
        rc, cfg_file = self._run(tmp_path, "format=flac", "artist_first=true")
        assert rc == cli.EXIT_OK
        saved = json.loads(cfg_file.read_text())
        assert saved["format"] == "flac"
        assert saved["artist_first"] is True

    def test_bad_value_is_usage_error(self, tmp_path, capsys):
        rc, _ = self._run(tmp_path, "format=wma")
        assert rc == cli.EXIT_USAGE

    def test_unknown_key_is_usage_error(self, tmp_path, capsys):
        rc, _ = self._run(tmp_path, "volume=11")
        assert rc == cli.EXIT_USAGE

    def test_internal_state_is_hidden_from_output(self, tmp_path, capsys):
        rc, _ = self._run(tmp_path, as_json=True)
        shown = json.loads(capsys.readouterr().out)
        assert "star_prompt_shown" not in shown
        assert "version" not in shown


class TestStatusCommand:
    def test_reads_manifest_basenames(self, tmp_path, capsys):
        (tmp_path / sd.MANIFEST_FILENAME).write_text(
            json.dumps({"id": "a", "file": "here.mp3"})
            + "\n"
            + json.dumps({"id": "b", "file": "gone.mp3"})
            + "\n"
        )
        (tmp_path / "here.mp3").write_bytes(b"x")
        rc = cli.cmd_status(SimpleNamespace(folder=str(tmp_path), json=True))
        assert rc == cli.EXIT_OK
        payload = json.loads(capsys.readouterr().out)
        assert payload["audio_files"] == 1
        assert payload["recorded_but_missing"] == 1
        assert payload["download_in_progress"] is False


class TestBinaryDispatch:
    """The one binary serves both personalities; these drive the real
    dispatch through a subprocess exactly as a shell would."""

    def _run(self, *argv):
        return subprocess.run(
            [sys.executable, os.path.join(REPO_ROOT, "Spotify_Downloader.py"), *argv],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=REPO_ROOT,
        )

    def test_version_via_dispatch(self):
        result = self._run("--version")
        assert result.returncode == 0
        assert result.stdout.strip() == f"sunnify {sd.__version__}"

    def test_help_lists_all_commands(self):
        result = self._run("--help")
        assert result.returncode == 0
        for command in ("download", "info", "status", "config", "doctor"):
            assert command in result.stdout

    def test_unknown_command_is_usage_error(self):
        result = self._run("download")  # missing url
        assert result.returncode == cli.EXIT_USAGE

    def test_typoed_command_suggests_instead_of_launching_gui(self):
        result = self._run("downlaod", "some-url")
        assert result.returncode == cli.EXIT_USAGE
        assert "did you mean 'download'" in result.stderr

    def test_typoed_command_is_case_insensitive(self):
        result = self._run("Download", "some-url")
        assert result.returncode == cli.EXIT_USAGE
        assert "did you mean 'download'" in result.stderr

    def test_unknown_word_is_rejected_not_swallowed(self):
        result = self._run("upgrade")
        assert result.returncode == cli.EXIT_USAGE
        assert "unknown command 'upgrade'" in result.stderr

    def test_help_command_alias(self):
        result = self._run("help")
        assert result.returncode == 0
        assert "usage: sunnify" in result.stdout

    def test_help_command_with_topic(self):
        result = self._run("help", "download")
        assert result.returncode == 0
        assert "usage: sunnify download" in result.stdout
