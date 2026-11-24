"""Security regressions: each test pins one hardening fix from the 3.0 audit."""

from __future__ import annotations

import contextlib
import json
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from sunnify import history, net, updates


class TestOutputTemplateInjection:
    """A Spotify title (or playlist name) is part of yt-dlp's output template.

    yt-dlp expands "%(field)s" in a template, so a title like "%(uploader)s"
    used to become the YouTube uploader's name, and "%%" collapsed to "%": the
    file landed under a name the engine never looked for, and the track failed.
    """

    @pytest.mark.parametrize(
        "stem",
        ["%(uploader)s - Artist", "100% Pure Love - Crystal Waters", "a%%b - c", "%(id)s"],
    )
    def test_percent_signs_in_the_name_stay_literal(self, stem, tmp_path):
        from yt_dlp import YoutubeDL as RealYoutubeDL

        from sunnify.engine import MusicScraper

        seen = []

        class FakeYDL:
            def __init__(self, opts):
                seen.append(opts)

            def __enter__(self):
                return self

            def __exit__(self, *_exc):
                return False

            def extract_info(self, *_a, **_k):
                return {}

        scraper = MusicScraper()
        destination = str(tmp_path / f"{stem}.mp3")
        with (
            patch("sunnify.tools.get_ffmpeg_path", return_value=str(tmp_path)),
            patch("sunnify.engine.YoutubeDL", FakeYDL),
            patch.object(scraper, "_select_youtube_match", return_value="https://youtu.be/x"),
            contextlib.suppress(RuntimeError),
        ):
            scraper.download_track_audio("ytsearch1:q", destination)
        template = next(o["outtmpl"] for o in seen if "outtmpl" in o)
        info = {"id": "VIDEO", "ext": "mp3", "title": "t", "uploader": "EVIL/../x"}
        with RealYoutubeDL({"quiet": True, "outtmpl": template}) as ydl:
            produced = ydl.prepare_filename(info)
        assert os.path.basename(produced) == f"{stem}.mp3"


class TestBoundedFetch:
    def _response(self, *, status=200, length=None, chunks=(b"img",)):
        resp = MagicMock(status_code=status)
        resp.headers = {"content-length": str(length)} if length is not None else {}
        resp.iter_content.return_value = list(chunks)
        return resp

    @pytest.mark.parametrize(
        "url", [None, "", "file:///etc/passwd", "javascript:alert(1)", "ftp://x/y", "//cdn/x"]
    )
    def test_only_http_urls_are_fetched(self, url):
        with patch("sunnify.net.requests.get") as get:
            assert net.fetch_bytes(url) is None
        get.assert_not_called()

    def test_declared_oversize_is_refused_without_reading(self):
        resp = self._response(length=net.MAX_IMAGE_BYTES + 1)
        with patch("sunnify.net.requests.get", return_value=resp):
            assert net.fetch_bytes("https://i.scdn.co/image/x") is None
        resp.iter_content.assert_not_called()
        resp.close.assert_called_once()

    def test_a_lying_content_length_is_still_capped(self):
        resp = self._response(length=10, chunks=[b"x" * 6, b"x" * 6])
        with patch("sunnify.net.requests.get", return_value=resp):
            assert net.fetch_bytes("https://i.scdn.co/image/x", limit=10) is None
        resp.close.assert_called_once()

    def test_a_normal_image_comes_back(self):
        resp = self._response(length=6, chunks=[b"abc", b"def"])
        with patch("sunnify.net.requests.get", return_value=resp) as get:
            assert net.fetch_bytes("https://i.scdn.co/image/x") == b"abcdef"
        assert get.call_args.kwargs["stream"] is True

    def test_errors_and_non_200_are_none(self):
        with patch("sunnify.net.requests.get", return_value=self._response(status=404)):
            assert net.fetch_bytes("https://i.scdn.co/image/x") is None


class TestUpdateLink:
    """The update toast opens whatever URL the release check returns."""

    @pytest.mark.parametrize(
        "candidate",
        [
            "https://evil.example/sunnify-3.1.exe",
            "http://github.com/sunnypatell/x",  # downgraded
            "https://github.com.evil.example/x",
            "file:///C:/Windows/System32/calc.exe",
            "javascript:alert(1)",
            None,
            42,
        ],
    )
    def test_anything_but_github_https_falls_back(self, candidate):
        assert updates._release_url(candidate) == updates._RELEASES_PAGE

    def test_a_github_release_link_is_kept(self):
        url = "https://github.com/sunnypatell/sunnify-spotify-downloader/releases/tag/v3.1.0"
        assert updates._release_url(url) == url

    def test_check_for_update_applies_it(self):
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"tag_name": "v99.0.0", "html_url": "https://evil.example/x"}
        with patch("requests.get", return_value=resp):
            assert updates._check_for_update("3.0.0") == ("99.0.0", updates._RELEASES_PAGE)

    def test_the_toast_refuses_to_open_non_https(self, monkeypatch):
        from sunnify.gui import dialogs

        opened = []
        monkeypatch.setattr(
            "sunnify.gui.dialogs.QDesktopServices",
            SimpleNamespace(openUrl=lambda url: opened.append(url) or True),
        )
        assert dialogs._open_url("file:///C:/evil.exe") is False
        assert opened == []


class TestOpenFolder:
    """Folder paths come from config.json and history.json; opening a file would run it."""

    @pytest.fixture
    def opened(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            "sunnify.gui.dialogs.QDesktopServices",
            SimpleNamespace(openUrl=lambda url: calls.append(url.toLocalFile()) or True),
        )
        return calls

    def test_a_file_is_never_handed_to_the_os(self, tmp_path, opened):
        from sunnify.gui import dialogs

        payload = tmp_path / "evil.exe"
        payload.write_bytes(b"MZ")
        assert dialogs.open_folder(str(payload)) is False
        assert dialogs.open_folder(str(payload), create=True) is False
        assert opened == []

    def test_a_missing_folder_is_not_recreated_unless_asked(self, tmp_path, opened):
        from sunnify.gui import dialogs

        gone = tmp_path / "deleted playlist"
        assert dialogs.open_folder(str(gone)) is False
        assert not gone.exists()
        assert dialogs.open_folder(str(gone), create=True) is True
        assert gone.is_dir() and len(opened) == 1


class TestRichTextInjection:
    """Playlist names, titles and artists are other people's text: never render them as HTML."""

    HOSTILE = '<h1 style="font-size:200px">FREE</h1><img src="file:///C:/x.png">'

    def test_window_labels_are_plain_text(self, qapp, monkeypatch):
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QLabel

        from sunnify.gui.window import MainWindow

        monkeypatch.setattr("sunnify.updates.UpdateCheckThread.start", lambda _self: None)
        win = MainWindow()
        win.update_AlbumName(self.HOSTILE)
        win.update_song_META({"title": self.HOSTILE, "artists": self.HOSTILE, "cover": ""})
        labels = win.findChildren(QLabel)
        assert labels
        assert all(label.textFormat() == Qt.TextFormat.PlainText for label in labels)
        assert self.HOSTILE in win.AlbumName.text()

    def test_tooltips_are_escaped(self):
        from sunnify.gui.dialogs import plain_tooltip

        tip = plain_tooltip(self.HOSTILE)
        assert "<h1" not in tip and "&lt;h1" in tip
        assert plain_tooltip("") == ""

    def test_dialog_labels_are_plain_text(self, qapp):
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QLabel

        from sunnify.gui.dialogs import HistoryDialog, SettingsDialog, UpdateNotifier

        for dlg in (
            SettingsDialog(None, {"download_path": self.HOSTILE}),
            HistoryDialog(None, [{"url": "u", "name": self.HOSTILE}]),
            UpdateNotifier(None, "3.0.0", self.HOSTILE, "https://github.com/x"),
        ):
            assert all(
                lbl.textFormat() == Qt.TextFormat.PlainText for lbl in dlg.findChildren(QLabel)
            )


class TestCorruptLocalFiles:
    """Hand-edited or truncated files must degrade, never crash a view or a command."""

    def test_history_numbers_that_are_not_numbers(self):
        with open(history.history_path(), "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "entries": [
                        {
                            "url": "u",
                            "started_at": "yesterday",
                            "finished_at": float("inf"),
                            "landed": -5,
                            "failed": True,
                            "name": ["not", "text"],
                        }
                    ]
                },
                fh,
            )
        (entry,) = history.load()
        assert (entry["started_at"], entry["finished_at"]) == (0.0, 0.0)
        assert (entry["landed"], entry["failed"], entry["name"]) == (0, 0, "")

    def test_status_skips_manifest_lines_that_are_not_records(self, tmp_path, capsys):
        import sunnify_cli as cli
        from sunnify.engine import MANIFEST_FILENAME

        (tmp_path / MANIFEST_FILENAME).write_text(
            '["a list"]\n42\n{"id": "a", "file": 7}\n{"id": "b", "file": "here.mp3"}\n',
            encoding="utf-8",
        )
        (tmp_path / "here.mp3").write_bytes(b"x")
        assert cli.cmd_status(SimpleNamespace(folder=str(tmp_path), json=True)) == cli.EXIT_OK
        payload = json.loads(capsys.readouterr().out)
        assert payload["manifest_entries"] == 1
