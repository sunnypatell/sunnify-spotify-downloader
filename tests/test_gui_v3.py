"""Tests for the 3.0 desktop UI: theme, language, history, paste/drop, layout guards."""

from __future__ import annotations

import os
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from sunnify import __version__, config, history, i18n
from sunnify.gui import theme

ALBUM = "https://open.spotify.com/album/4aawyAB9vmqN3uQ7FjRGTy"
TRACK = "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT"


@pytest.fixture(autouse=True)
def _no_update_thread(monkeypatch):
    monkeypatch.setattr("sunnify.updates.UpdateCheckThread.start", lambda _self: None)


def _contrast(fg: str, bg: str) -> float:
    def lum(hex_color):
        h = hex_color.lstrip("#")
        rgb = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]
        lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]

    a, b = sorted((lum(fg), lum(bg)), reverse=True)
    return (a + 0.05) / (b + 0.05)


class TestTheme:
    @pytest.mark.parametrize("palette", [theme.DARK, theme.LIGHT], ids=lambda p: p.name)
    def test_text_pairs_clear_wcag_aa(self, palette):
        pairs = {
            "text on card": (palette.text, palette.window),
            "text on panel": (palette.text, palette.surface),
            "muted on card": (palette.muted, palette.window),
            "muted on panel": (palette.muted, palette.surface),
            "button text on accent": (palette.accent_text, palette.accent),
            "stop text on danger": (palette.danger_text, palette.danger),
            "accent ink on card": (palette.accent_ink, palette.window),
        }
        for name, (fg, bg) in pairs.items():
            assert _contrast(fg, bg) >= 4.5, f"{palette.name}: {name} is {_contrast(fg, bg):.2f}"

    @pytest.mark.parametrize("palette", [theme.DARK, theme.LIGHT], ids=lambda p: p.name)
    def test_stylesheet_assets_ship(self, palette):
        for name in ("check.svg", f"chevron-{palette.name}.svg"):
            path = theme.asset(name)
            assert os.path.isfile(path), path
            assert path in theme.app_stylesheet(palette) or name == "check.svg"

    def test_explicit_choice_wins_over_the_system(self):
        assert theme.resolve("light") is theme.LIGHT
        assert theme.resolve("dark") is theme.DARK
        assert theme.resolve("system") in (theme.DARK, theme.LIGHT)

    def test_no_stylesheet_size_rule_overrides_fixed_button_heights(self):
        """A QSS min-height on QPushButton silently beat setFixedHeight (44px -> 30px)."""
        for p in (theme.DARK, theme.LIGHT):
            for sheet in (theme.app_stylesheet(p), theme.window_stylesheet(p)):
                for block in sheet.split("}"):
                    if "QPushButton" in block.split("{")[0]:
                        assert "min-height" not in block and "max-height" not in block


class TestWindowLayout:
    def test_buttons_keep_their_designed_heights(self, qapp):
        from sunnify.gui.window import MainWindow

        win = MainWindow()
        win.show()
        qapp.processEvents()
        assert win.DownloadBtn.height() == 40
        assert win.PlaylistLink.height() == 40
        assert win.OpenFolderBtn.height() == 32

    @pytest.mark.parametrize("lang", ["en", "ms"])
    def test_header_names_the_author_in_full(self, qapp, lang):
        """The license requires attribution: the byline must fit, not be clipped."""
        from sunnify.gui.window import MainWindow

        i18n.set_language(lang)
        win = MainWindow()
        win.show()
        qapp.processEvents()
        assert "Sunny Patel" in win.author.text()
        # the layout grants each label at least the width its own text asks for
        assert win.author.width() >= win.author.sizeHint().width()
        assert win.title.width() >= win.title.sizeHint().width()
        assert win.version.text() == f"v{__version__}"
        # and the floating window buttons never sit on top of the title
        controls = win.SettingsBtn.parentWidget().geometry()
        assert win.version.geometry().right() < controls.left()

    @pytest.mark.parametrize("lang", ["en", "ms"])
    def test_everything_fits_the_fixed_card(self, qapp, lang):
        """The card is 460px tall by design; content asking for more gets squeezed
        (the progress bar ended up on top of the song name before this test)."""
        from sunnify.gui.window import MainWindow

        i18n.set_language(lang)
        win = MainWindow()
        win.show()
        win.statusMsg.setText(i18n.t("engine.resuming", count=120))
        win.update_AlbumName("Today's Top Hits - Spotify")
        win.MainSongName.setText("Blinding Lights - The Weeknd")
        qapp.processEvents()
        # height-for-width at the real width: wrapping labels ask for their actual lines
        assert win.frame.layout().totalHeightForWidth(win.frame.width()) <= win.frame.height()
        now = win.nowPanel
        assert now.height() >= now.layout().totalHeightForWidth(now.width())

    @pytest.mark.parametrize("lang", ["en", "ms"])
    def test_option_labels_are_not_clipped(self, qapp, lang):
        from sunnify.gui.window import MainWindow

        i18n.set_language(lang)
        win = MainWindow()
        win.show()
        qapp.processEvents()
        for box in (win.showPreviewCheck, win.AddMetaDataCheck, win.OpenFolderBtn, win.HistoryBtn):
            assert box.width() >= box.sizeHint().width(), box.text()


class TestLanguageAndThemeLive:
    def _window_after(self, monkeypatch, **changes):
        from PyQt6.QtWidgets import QDialog

        from sunnify.gui.window import MainWindow

        class FakeDialog:
            def __init__(self, _parent, cfg):
                self.cfg = dict(cfg)

            def exec(self):
                return QDialog.DialogCode.Accepted

            def result_config(self):
                return {**self.cfg, **changes}

        monkeypatch.setattr("sunnify.gui.dialogs.SettingsDialog", FakeDialog)
        win = MainWindow()
        win.open_settings()
        return win

    def test_language_switch_retranslates_without_restart(self, qapp, monkeypatch):
        win = self._window_after(monkeypatch, language="ms")
        assert win.DownloadBtn.text() == "Muat turun"
        assert win.PlaylistLink.placeholderText() == "Tampal pautan Spotify di sini"
        assert win.statusMsg.text() == "Tetapan disimpan"
        assert config.load_config()["language"] == "ms"

    def test_theme_switch_restyles_without_restart(self, qapp, monkeypatch):
        win = self._window_after(monkeypatch, theme="light")
        assert theme.current() is theme.LIGHT
        assert theme.LIGHT.window in win.centralwidget.styleSheet()


class TestRememberedToggles:
    def test_add_tags_and_preview_survive_a_restart(self, qapp):
        from sunnify.gui.window import MainWindow

        win = MainWindow()
        assert win.AddMetaDataCheck.isChecked()  # tags on by default now
        win.AddMetaDataCheck.setChecked(False)
        win.showPreviewCheck.setChecked(True)
        again = MainWindow()
        assert not again.AddMetaDataCheck.isChecked()
        assert again.showPreviewCheck.isChecked()
        assert again.SONGINFORMATION.width() > 0


class TestPasteAndDrop:
    def _window(self, monkeypatch, tmp_path):
        from sunnify.gui.window import MainWindow

        started = []

        class FakeThread:
            def __init__(self, url, folder, cancel_event=None, **_opts):
                self.url, self.cancel = url, cancel_event
                self.progress_update = MagicMock()
                self.finished = MagicMock()
                self.scraper = MagicMock()

            def start(self):
                started.append(self.url)

            def isRunning(self):
                return True

            def request_cancel(self):
                self.cancel.set()

            def deleteLater(self):
                pass

        monkeypatch.setattr("sunnify.engine.ScraperThread", FakeThread)
        monkeypatch.setattr("sunnify.tools.get_ffmpeg_path", lambda: str(tmp_path))
        win = MainWindow()
        win._download_path_set = True
        win.download_path = str(tmp_path)
        return win, started

    def test_paste_lines_up_a_link_when_idle(self, qapp, monkeypatch, tmp_path):
        win, started = self._window(monkeypatch, tmp_path)
        qapp.clipboard().setText(f"look at this {ALBUM} !")
        win._paste_from_clipboard()
        assert win.PlaylistLink.text() == ALBUM
        assert started == []
        assert "press Download" in win.statusMsg.text()

    def test_paste_queues_while_downloading(self, qapp, monkeypatch, tmp_path):
        win, started = self._window(monkeypatch, tmp_path)
        win.PlaylistLink.setText(ALBUM)
        win.on_returnButton()
        qapp.clipboard().setText(TRACK)
        win._paste_from_clipboard()
        assert started == [ALBUM] and list(win._queue) == [TRACK]

    def test_paste_without_a_spotify_link_says_so(self, qapp, monkeypatch, tmp_path):
        win, _ = self._window(monkeypatch, tmp_path)
        qapp.clipboard().setText("https://example.com/song")
        win._paste_from_clipboard()
        assert win.statusMsg.text() == "No Spotify link found there"
        assert win.PlaylistLink.text() == ""

    def test_drop_takes_the_link(self, qapp, monkeypatch, tmp_path):
        from PyQt6.QtCore import QMimeData

        win, _ = self._window(monkeypatch, tmp_path)
        mime = QMimeData()
        mime.setText(TRACK)
        event = SimpleNamespace(mimeData=lambda: mime, acceptProposedAction=lambda: None)
        win.dropEvent(event)
        assert win.PlaylistLink.text() == TRACK


class TestHistoryRecording:
    def _finished(self, monkeypatch, tmp_path, *, scraper, stopped=False):
        from sunnify.gui.window import MainWindow

        win = MainWindow()
        win._current_link = ALBUM
        win._is_downloading = True
        win._cancel_event = threading.Event()
        if stopped:
            win._cancel_event.set()
        win.scraper_thread = SimpleNamespace(scraper=scraper, deleteLater=lambda: None)
        win.thread_finished()
        return win

    def test_a_finished_run_lands_in_history_and_open_folder(self, qapp, monkeypatch, tmp_path):
        scraper = SimpleNamespace(
            output_folder=str(tmp_path),
            display_name="After Hours - The Weeknd",
            _failed_tracks=["one"],
            counter=5,
        )
        win = self._finished(monkeypatch, tmp_path, scraper=scraper)
        (entry,) = history.load()
        assert entry["name"] == "After Hours - The Weeknd"
        assert entry["kind"] == "album"
        assert (entry["landed"], entry["failed"], entry["status"]) == (4, 1, "partial")
        assert win._last_folder == str(tmp_path)

    def test_a_stopped_run_is_recorded_as_stopped(self, qapp, monkeypatch, tmp_path):
        scraper = SimpleNamespace(
            output_folder=str(tmp_path), display_name="x", _failed_tracks=[], counter=1
        )
        self._finished(monkeypatch, tmp_path, scraper=scraper, stopped=True)
        assert history.load()[0]["status"] == "stopped"

    def test_a_mock_or_dead_scraper_never_breaks_finishing(self, qapp, monkeypatch, tmp_path):
        win = self._finished(monkeypatch, tmp_path, scraper=MagicMock())
        assert not win._is_downloading
        entry = history.load()[0]
        assert entry["name"] == ALBUM and entry["folder"] == ""

    def test_history_dialog_downloads_again_and_never_defaults_to_clear(self, qapp):
        from sunnify.gui.dialogs import HistoryDialog

        history.record(url=ALBUM, name="A", folder="")
        dlg = HistoryDialog(None)
        assert dlg._again_btn.isDefault() and not dlg._clear_btn.autoDefault()
        dlg._again_selected()
        assert dlg.requested_url == ALBUM
        dlg._clear()
        assert history.load() == [] and not dlg._clear_btn.isEnabled()

    def test_history_lines_read_in_the_current_language(self):
        from sunnify.gui.dialogs import HistoryDialog

        entry = {"name": "A", "finished_at": 0, "status": "failed", "landed": 0, "failed": 3}
        i18n.set_language("ms")
        assert HistoryDialog.describe(entry) == "A\n?  ·  Gagal  ·  0 disimpan  ·  3 gagal"


class TestSettingsDialogV3:
    def test_new_settings_round_trip(self, qapp):
        from sunnify.gui.dialogs import SettingsDialog

        dlg = SettingsDialog(
            None, {"language": "ms", "theme": "light", "lyrics": True, "notify": False}
        )
        out = dlg.result_config()
        assert (out["language"], out["theme"], out["lyrics"], out["notify"]) == (
            "ms",
            "light",
            True,
            False,
        )
        fresh = SettingsDialog(None, {}).result_config()
        assert (fresh["language"], fresh["theme"], fresh["lyrics"], fresh["notify"]) == (
            "auto",
            "system",
            False,
            True,
        )

    def test_unset_folder_placeholder_is_never_saved_as_a_path(self, qapp):
        from sunnify.gui.dialogs import SettingsDialog

        assert "download_path" not in SettingsDialog(None, {}).result_config()

    def test_filename_preview_uses_the_chosen_format(self, qapp):
        from sunnify.gui.dialogs import SettingsDialog

        dlg = SettingsDialog(None, {"format": "flac"})
        assert dlg._filename_preview.text() == "Song - Artist.flac"

    def test_style_survives_a_language_switch(self, qapp):
        """The style combo stores values, not labels, so Malay text maps back correctly."""
        from sunnify.gui.dialogs import SettingsDialog

        i18n.set_language("ms")
        dlg = SettingsDialog(None, {"artist_first": True})
        assert dlg._filename_style_cb.currentText() == "Artis - Lagu"
        out = dlg.result_config()
        assert out["artist_first"] is True and out["title_only"] is False
