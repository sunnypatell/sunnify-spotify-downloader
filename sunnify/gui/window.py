"""The main window: a frameless card with a song panel that slides out beside it.

The window is a fixed 750 x 500 composition (WINDOW_W x WINDOW_H) on a
transparent background: the main card on the left, and the song information
panel tucked behind its right edge, sliding out when "Show preview" is on.
Inside each card everything is laid out by Qt layouts, so text in either
language and at any window size gets the room it needs.

Widget attribute names (PlaylistLink, DownloadBtn, statusMsg, CounterLabel,
SONGINFORMATION, ...) are the window's public surface: the tests, the CLI's
probe scripts and older forks address them by name, so they are kept.
"""

from __future__ import annotations

import collections
import os
import sys
import threading
import time
import webbrowser

from PyQt6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QRect,
    QSize,
    Qt,
    QThread,
    QTimer,
    pyqtSlot,
)
from PyQt6.QtGui import (
    QColor,
    QCursor,
    QIcon,
    QImage,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPixmap,
    QShortcut,
)
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStyle,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from spotifydown_api import detect_spotify_url_type
from sunnify import __version__, config, engine, history, i18n, net, tagging, tools
from sunnify.gui import dialogs, scale, theme
from sunnify.i18n import t
from sunnify.logs import log
from sunnify.qt import Signal
from sunnify.updates import UpdateCheckThread

# geometry of the two cards inside the transparent window
_CARD = QRect(24, 20, 340, 460)
_PANEL_X, _PANEL_Y, _PANEL_H = 352, 36, 428
_PANEL_OPEN_W = 374
_COVER = 196


def resource_path(name: str) -> str:
    """A file shipped next to the app: the PyInstaller bundle, or the source tree."""
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    return os.path.join(base, name)


def app_icon() -> QIcon:
    path = resource_path("app.png")
    icon = QIcon(path) if os.path.exists(path) else QIcon()
    style = QApplication.style() if QApplication.instance() is not None else None
    if icon.isNull() and style is not None:
        icon = style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
    return icon


def rounded_pixmap(image: QImage, side: int, radius: int, dpr: float) -> QPixmap:
    """Centre-crop to a square and round the corners, sharp on high-dpi screens."""
    px = max(1, int(side * dpr))
    src = QPixmap.fromImage(image).scaled(
        px,
        px,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    out = QPixmap(px, px)
    out.fill(Qt.GlobalColor.transparent)
    painter = QPainter(out)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(0, 0, px, px, radius * dpr, radius * dpr)
    painter.setClipPath(path)
    painter.drawPixmap((px - src.width()) // 2, (px - src.height()) // 2, src)
    painter.end()
    out.setDevicePixelRatio(dpr)
    return out


class DownloadThumbnail(QThread):
    thumbnail_ready = Signal(bytes)  # Signal to safely update UI from main thread

    def __init__(self, url, main_UI):
        super().__init__()
        self.url = url
        self.main_UI = main_UI
        self.thumbnail_ready.connect(self._update_ui)

    def run(self):
        data = net.fetch_bytes(self.url, timeout=10)
        if data:
            self.thumbnail_ready.emit(data)

    def _update_ui(self, data):
        """Update UI from main thread via signal."""
        pic = QImage()
        if not pic.loadFromData(data):
            return
        label = self.main_UI.CoverImg
        label.setPixmap(rounded_pixmap(pic, _COVER, 16, label.devicePixelRatioF()))
        label.show()


class MainWindow(QMainWindow):
    def __init__(self):
        """MainWindow constructor"""
        super().__init__()
        # Load persisted user config so format/quality/folder survive restarts
        self._config = config.load_config()
        self.download_path = self._config.get("download_path") or self._get_default_download_path()
        self._download_path_set = bool(self._config.get("download_path"))
        # Keep references to running threads to prevent GC crashes
        self._active_threads: list[QThread] = []
        self._is_downloading = False  # Track download state for stop button
        self._queue: collections.deque[str] = collections.deque()
        self._current_link = ""
        self._started_at = 0.0
        self._last_folder: str | None = None
        self._tray: QSystemTrayIcon | None = None
        self._cancel_event = threading.Event()  # Event for cooperative thread cancellation
        self.m_drag = False

        self.setWindowTitle("Sunnify")
        self.setWindowIcon(app_icon())
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(scale.WINDOW_W, scale.WINDOW_H)
        self.setAcceptDrops(True)

        self._build_ui()
        self._apply_theme()
        self._retranslate()
        self.restore_preview()

        self.PlaylistLink.returnPressed.connect(self._on_link_entered)
        self.DownloadBtn.clicked.connect(self.on_returnButton)
        self.PasteBtn.clicked.connect(self._paste_from_clipboard)
        self.OpenFolderBtn.clicked.connect(self._open_output_folder)
        self.showPreviewCheck.stateChanged.connect(self.show_preview)
        self.AddMetaDataCheck.toggled.connect(self._remember_toggle("write_tags"))
        self.Closed.clicked.connect(self.exitprogram)
        self.MinimizeBtn.clicked.connect(self.showMinimized)
        self.Select_Home.clicked.connect(self.Linkedin)
        self.SettingsBtn.clicked.connect(self.open_settings)
        self.HistoryBtn.clicked.connect(self.open_history)
        for keys, slot in (
            ("Ctrl+,", self.open_settings),
            ("Ctrl+H", self.open_history),
            ("Ctrl+Q", self.exitprogram),
        ):
            QShortcut(QKeySequence(keys), self).activated.connect(slot)

        # check for a newer release in the background; fail-silent, shows a toast only if found
        self._update_thread = UpdateCheckThread(__version__)
        self._update_thread.update_available.connect(self._show_update_notifier)
        self._active_threads.append(self._update_thread)
        self._update_thread.start()

    # ---- construction -------------------------------------------------

    def _build_ui(self):
        self.centralwidget = QWidget(self)
        self.centralwidget.setObjectName("centralwidget")
        self.setCentralWidget(self.centralwidget)

        # the song panel first so the card paints over its tucked-in edge
        self.SONGINFORMATION = QFrame(self.centralwidget)
        self.SONGINFORMATION.setObjectName("SONGINFORMATION")
        self.SONGINFORMATION.setGeometry(_PANEL_X, _PANEL_Y, 0, _PANEL_H)
        self._build_song_panel(self.SONGINFORMATION)

        self.frame = QFrame(self.centralwidget)
        self.frame.setObjectName("frame")
        self.frame.setGeometry(_CARD)
        self._build_card(self.frame)

        for card in (self.frame, self.SONGINFORMATION):
            shadow = QGraphicsDropShadowEffect(card)
            shadow.setBlurRadius(36)
            shadow.setOffset(0, 10)
            card.setGraphicsEffect(shadow)
        self.SONGINFORMATION.lower()
        self.frame.raise_()
        dialogs.plain_text_labels(self)

    @staticmethod
    def _icon_button(name: str, glyph: str) -> QPushButton:
        btn = QPushButton(glyph)
        btn.setObjectName(name)
        btn.setFixedSize(28, 28)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        return btn

    def _build_card(self, card: QFrame):
        v = QVBoxLayout(card)
        v.setContentsMargins(22, 18, 22, 12)
        v.setSpacing(9)

        # header: mark, name + byline, window buttons
        header = QHBoxLayout()
        header.setSpacing(10)
        self.logo = QLabel("S")
        self.logo.setObjectName("logo")
        self.logo.setFixedSize(36, 36)
        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(self.logo)
        self.title = QLabel("Sunnify")
        self.title.setObjectName("title")
        self.version = QLabel(f"v{__version__}")
        self.version.setObjectName("version")
        header.addWidget(self.title)
        header.addWidget(self.version, 0, Qt.AlignmentFlag.AlignVCenter)
        header.addStretch(1)
        v.addLayout(header)
        # the byline (the license's attribution) gets the card's full width, so it
        # never clips in a longer language or a wider fallback font
        self.author = QLabel()
        self.author.setObjectName("author")
        v.addWidget(self.author)

        # window buttons float over the header's top-right corner, so the byline
        # below them gets the card's full width in either language
        controls = QWidget(card)
        controls.setObjectName("windowControls")
        cl = QHBoxLayout(controls)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(2)
        self.SettingsBtn = self._icon_button("SettingsBtn", "⚙︎")
        self.MinimizeBtn = self._icon_button("MinimizeBtn", "\u2013")
        self.Closed = self._icon_button("Closed", "✕")
        for btn in (self.SettingsBtn, self.MinimizeBtn, self.Closed):
            cl.addWidget(btn)
        controls.adjustSize()
        controls.move(_CARD.width() - 16 - controls.width(), 18)
        controls.raise_()

        # link + paste, then the one big button
        link_row = QHBoxLayout()
        link_row.setSpacing(8)
        self.PlaylistLink = QLineEdit()
        self.PlaylistLink.setObjectName("PlaylistLink")
        self.PlaylistLink.setFixedHeight(40)
        self.PlaylistLink.setClearButtonEnabled(True)
        link_row.addWidget(self.PlaylistLink, 1)
        self.PasteBtn = QPushButton()
        self.PasteBtn.setObjectName("PasteBtn")
        self.PasteBtn.setFixedHeight(40)
        self.PasteBtn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        link_row.addWidget(self.PasteBtn)
        v.addLayout(link_row)

        self.DownloadBtn = QPushButton()
        self.DownloadBtn.setObjectName("DownloadBtn")
        self.DownloadBtn.setFixedHeight(40)
        self.DownloadBtn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        v.addWidget(self.DownloadBtn)

        self.statusMsg = QLabel()
        self.statusMsg.setObjectName("statusMsg")
        self.statusMsg.setWordWrap(True)
        self.statusMsg.setMinimumHeight(32)
        self.statusMsg.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.statusMsg.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        v.addWidget(self.statusMsg)

        # what is happening right now
        now = QFrame()
        now.setObjectName("nowPanel")
        nv = QVBoxLayout(now)
        nv.setContentsMargins(14, 10, 14, 10)
        nv.setSpacing(5)
        self.AlbumName = QLabel()
        self.AlbumName.setObjectName("AlbumName")
        self.AlbumName.setWordWrap(True)
        self.MainSongName = QLabel()
        self.MainSongName.setObjectName("MainSongName")
        self.MainSongName.setWordWrap(True)
        self.MainSongName.setMinimumHeight(18)
        self.SongDownloadprogress = QProgressBar()
        self.SongDownloadprogress.setObjectName("SongDownloadprogress")
        self.SongDownloadprogress.setTextVisible(False)
        self.SongDownloadprogress.setFixedHeight(6)
        self.SongDownloadprogress.setValue(0)
        self.CounterLabel = QLabel()
        self.CounterLabel.setObjectName("CounterLabel")
        for w in (self.AlbumName, self.MainSongName, self.SongDownloadprogress, self.CounterLabel):
            nv.addWidget(w)
        v.addWidget(now)
        self.nowPanel = now

        options = QHBoxLayout()
        options.setSpacing(14)
        self.showPreviewCheck = QCheckBox()
        self.showPreviewCheck.setObjectName("showPreviewCheck")
        self.AddMetaDataCheck = QCheckBox()
        self.AddMetaDataCheck.setObjectName("AddMetaDataCheck")
        self.AddMetaDataCheck.setChecked(self._config.get("write_tags", True))
        options.addWidget(self.showPreviewCheck)
        options.addWidget(self.AddMetaDataCheck)
        options.addStretch(1)
        v.addLayout(options)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.OpenFolderBtn = QPushButton()
        self.OpenFolderBtn.setObjectName("OpenFolderBtn")
        self.HistoryBtn = QPushButton()
        self.HistoryBtn.setObjectName("HistoryBtn")
        for btn in (self.OpenFolderBtn, self.HistoryBtn):
            btn.setFixedHeight(32)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            actions.addWidget(btn, 1)
        v.addLayout(actions)

        v.addStretch(1)
        self.Select_Home = QPushButton()
        self.Select_Home.setObjectName("Select_Home")
        self.Select_Home.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        v.addWidget(self.Select_Home, 0, Qt.AlignmentFlag.AlignHCenter)

    def _build_song_panel(self, panel: QFrame):
        v = QVBoxLayout(panel)
        # the left 12px sit behind the main card
        v.setContentsMargins(36, 22, 24, 22)
        v.setSpacing(10)
        self.label_3 = QLabel()
        self.label_3.setObjectName("label_3")
        self.label_3.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(self.label_3)
        self.CoverImg = QLabel("♫")
        self.CoverImg.setObjectName("CoverImg")
        self.CoverImg.setFixedSize(_COVER, _COVER)
        self.CoverImg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(self.CoverImg, 0, Qt.AlignmentFlag.AlignHCenter)
        v.addSpacing(4)
        self.SongName = QLabel()
        self.SongName.setObjectName("SongName")
        self.SongName.setWordWrap(True)
        self.SongName.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ArtistNameText = QLabel()
        self.ArtistNameText.setObjectName("ArtistNameText")
        self.ArtistNameText.setWordWrap(True)
        self.ArtistNameText.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(self.SongName)
        v.addWidget(self.ArtistNameText)

        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(4)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.label_8 = QLabel()
        self.label_6 = QLabel()
        for caption in (self.label_8, self.label_6):
            caption.setProperty("caption", True)
        self.AlbumText = QLabel()
        self.AlbumText.setObjectName("AlbumText")
        self.AlbumText.setWordWrap(True)
        self.YearText = QLabel()
        self.YearText.setObjectName("YearText")
        form.addRow(self.label_8, self.AlbumText)
        form.addRow(self.label_6, self.YearText)
        v.addLayout(form)
        v.addStretch(1)
        self.SongDownloadprogressBar = QProgressBar()
        self.SongDownloadprogressBar.setObjectName("SongDownloadprogressBar")
        self.SongDownloadprogressBar.setTextVisible(False)
        self.SongDownloadprogressBar.setFixedHeight(4)
        self.SongDownloadprogressBar.setValue(0)
        v.addWidget(self.SongDownloadprogressBar)

    def _apply_theme(self):
        p = theme.use(self._config.get("theme", "system"))
        self.centralwidget.setStyleSheet(theme.window_stylesheet(p))
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(theme.app_stylesheet(p))
        for card in (self.frame, self.SONGINFORMATION):
            effect = card.graphicsEffect()
            if isinstance(effect, QGraphicsDropShadowEffect):
                effect.setColor(QColor(*p.shadow))

    def _retranslate(self):
        """Every static text, so a language change applies without a restart."""
        self.author.setText(t("main.author"))
        self._idle_placeholder = t("main.placeholder")
        self.PasteBtn.setText(t("main.paste"))
        self.PasteBtn.setToolTip(t("main.paste.tip"))
        self.DownloadBtn.setText(t("main.stop") if self._is_downloading else t("main.download"))
        self.showPreviewCheck.setText(t("main.preview"))
        self.AddMetaDataCheck.setText(t("main.tags"))
        self.AddMetaDataCheck.setToolTip(t("main.tags.tip"))
        self.OpenFolderBtn.setText(t("main.open_folder"))
        self.OpenFolderBtn.setToolTip(t("main.open_folder.tip"))
        self.HistoryBtn.setText(t("main.history"))
        self.Select_Home.setText(t("main.linkedin"))
        self.HistoryBtn.setToolTip(t("main.history.tip"))
        self.SettingsBtn.setToolTip(t("main.settings.tip"))
        self.MinimizeBtn.setToolTip(t("main.minimize.tip"))
        self.Closed.setToolTip(t("main.close.tip"))
        self.label_3.setText(t("panel.heading").upper())
        self.label_8.setText(t("panel.album"))
        self.label_6.setText(t("panel.released"))
        if not self._is_downloading:
            self.AlbumName.setText(t("main.idle"))
            self.statusMsg.setText(t("main.ready"))
            self.CounterLabel.setText(t("main.counter", done=0))
        self._update_queue_hint()

    # ---- notifications ------------------------------------------------

    @pyqtSlot(str, str)
    def _show_update_notifier(self, latest: str, url: str):
        if QApplication.activeModalWidget() is not None:
            # never stack on another toast; the check simply runs again next launch
            log.info("update notifier skipped: another modal dialog is active")
            return
        log.info("update available: %s -> %s; showing notifier", __version__, latest)
        dialogs.UpdateNotifier(self, __version__, latest, url).exec()

    @pyqtSlot(int)
    def _maybe_show_star_prompt(self, count: int):
        """One-time star ask the moment the first song of the user's first
        run lands on disk. Skipped after a Stop (a beg right then reads as
        nagging). Deferred cases (update toast on screen) retry naturally
        when the next song lands - the flag only persists once the dialog
        actually shows, so the one shot is never burned silently."""
        if self._config.get("star_prompt_shown"):
            return
        # count ticks per finished track either way, so a fully failed run
        # would otherwise beg for a star having saved nothing
        if count - self._failed_track_count() < 1:
            return
        if self._cancel_event.is_set():
            return
        if QApplication.activeModalWidget() is not None:
            # never stack on the update notifier; the next landed song retries
            log.info("star prompt deferred: another modal dialog is active")
            return
        # persist before showing so a crash mid-dialog can never re-prompt
        self._config["star_prompt_shown"] = True
        config.save_config(self._config)
        log.info("first song landed - showing one-time star prompt")
        dialogs.StarPromptNotifier(self).exec()

    def _notify_finished(self, name: str, landed: int, failed: int) -> None:
        """Tell the desktop a run ended while Sunnify sat in the background."""
        if not self._config.get("notify", True) or self.isActiveWindow():
            return
        QApplication.alert(self, 0)
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        if self._tray is None:
            self._tray = QSystemTrayIcon(self.windowIcon(), self)
            self._tray.messageClicked.connect(self._bring_to_front)
        body = t("notify.body", name=name, landed=landed)
        if failed:
            body += " " + t("notify.failed", failed=failed)
        self._tray.show()
        self._tray.showMessage(
            t("notify.title"), body, QSystemTrayIcon.MessageIcon.Information, 6000
        )
        # a tray icon that outlives its message is clutter
        QTimer.singleShot(9000, self._tray.hide)

    def _bring_to_front(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    # ---- folders ------------------------------------------------------

    def _get_default_download_path(self):
        """Get a sensible default download path that's writable."""
        # Try user's Music folder first
        home = os.path.expanduser("~")
        music_folder = os.path.join(home, "Music", "Sunnify")

        # On Windows, Music might be in a different location
        if sys.platform == "win32":
            try:
                import winreg

                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
                )
                music_folder = os.path.join(winreg.QueryValueEx(key, "My Music")[0], "Sunnify")
                winreg.CloseKey(key)
            except Exception:
                music_folder = os.path.join(home, "Music", "Sunnify")

        return music_folder

    def _ensure_download_path(self):
        """Ensure download path exists and is writable. Returns True if valid."""
        try:
            os.makedirs(self.download_path, exist_ok=True)
            # Test write access
            test_file = os.path.join(self.download_path, ".sunnify_test")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            return True
        except OSError as exc:
            log.error("download path not writable: %s (%s)", self.download_path, exc)
            return False

    def _prompt_download_location(self):
        """Prompt user to select download location. Returns True if selected."""
        folder = QFileDialog.getExistingDirectory(
            self,
            t("settings.choose_folder.title"),
            os.path.expanduser("~"),
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks,
        )
        if folder:
            self.download_path = dialogs.with_sunnify_subfolder(folder)
            self._download_path_set = True
            self._config["download_path"] = self.download_path
            config.save_config(self._config)
            return True
        return False

    def _open_output_folder(self):
        folder = (
            self._last_folder if self._last_folder and os.path.isdir(self._last_folder) else None
        )
        dialogs.open_folder(folder or self.download_path, create=folder is None)

    # ---- settings + history -------------------------------------------

    def open_settings(self):
        """Full settings dialog: folder, audio, naming, matching, language, look."""
        cfg_for_dialog = dict(self._config)
        cfg_for_dialog["download_path"] = self.download_path
        dialog = dialogs.SettingsDialog(self, cfg_for_dialog)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new = dialog.result_config()
            old_scale = self._config.get("ui_scale", "100")
            old_language = self._config.get("language", "auto")
            old_theme = self._config.get("theme", "system")
            if new.get("download_path"):
                self.download_path = new["download_path"]
                self._download_path_set = True
            self._config.update(
                {s.key: s.coerce(new.get(s.key, s.default)) for s in config.SETTINGS}
            )
            self._config["download_path"] = self.download_path
            config.save_config(self._config)
            if self._config.get("language") != old_language:
                i18n.set_language(i18n.resolve(self._config.get("language")))
                self._retranslate()
            if self._config.get("theme") != old_theme:
                self._apply_theme()
            self.statusMsg.setText(t("status.settings_saved"))
            if self._config.get("ui_scale") != old_scale:
                self._apply_new_ui_scale()

    def open_history(self):
        dialog = dialogs.HistoryDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.requested_url:
            self._take_links(dialog.requested_url)

    def _apply_new_ui_scale(self):
        """A new window size needs a fresh process; offer one when nothing would be cut short."""
        if self._is_downloading or not self._ask_restart():
            self.statusMsg.setText(t("status.scale_next_open"))
            return
        if scale.relaunch_app():
            QApplication.quit()
            return
        self.statusMsg.setText(t("status.scale_restart_failed"))

    def _ask_restart(self) -> bool:
        box = QMessageBox(self)
        box.setWindowTitle(t("restart.title"))
        box.setIcon(QMessageBox.Icon.Question)
        box.setText(t("restart.body"))
        restart = box.addButton(t("restart.now"), QMessageBox.ButtonRole.AcceptRole)
        box.addButton(t("restart.later"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(restart)
        box.exec()
        return box.clickedButton() is restart

    def _remember_toggle(self, key: str):
        def _save(checked: bool):
            self._config[key] = bool(checked)
            config.save_config(self._config)

        return _save

    # ---- starting, queueing, stopping -----------------------------------

    @pyqtSlot()
    def on_returnButton(self):
        # If already downloading, stop the download
        if self._is_downloading:
            self._stop_download()
            return

        links = self.PlaylistLink.text().split()
        if not links:
            self.statusMsg.setText(t("status.enter_url"))
            return

        if not tools.get_ffmpeg_path():
            self.statusMsg.setText(t("status.ffmpeg_missing"))
            QMessageBox.critical(
                self,
                t("ffmpeg.title"),
                t("ffmpeg.body", hint=tools.ffmpeg_install_hint()),
            )
            return

        cookies = self._config.get("cookies_file")
        problem = tools.cookies_problem(os.path.expanduser(cookies)) if cookies else None
        if problem:
            self.statusMsg.setText(t("status.cookies_unusable"))
            QMessageBox.warning(self, t("cookies.title"), t("cookies.body", problem=problem[1]))
            return

        # ALWAYS prompt for download location on first download
        if not self._download_path_set:
            self.statusMsg.setText(t("status.select_location"))
            if not self._prompt_download_location():
                self.statusMsg.setText(t("status.no_folder"))
                return

        # Verify the selected path is still writable
        if not self._ensure_download_path():
            self.statusMsg.setText(t("status.not_writable"))
            QMessageBox.warning(
                self, t("not_writable.title"), t("not_writable.body", path=self.download_path)
            )
            if not self._prompt_download_location():
                return

        bad = self._invalid_links(links)
        if bad:
            self.statusMsg.setText(t("status.not_spotify", link=bad[0]))
            return
        self._queue.extend(u for u in dict.fromkeys(links) if u != links[0])
        self._start_download(links[0])

    @staticmethod
    def _invalid_links(links: list[str]) -> list[str]:
        bad = []
        for link in links:
            try:
                url_type, item_id = detect_spotify_url_type(link)
            except ValueError:
                url_type, item_id = "unknown", None
            if url_type == "unknown" or not item_id:
                bad.append(link)
        return bad

    def _on_link_entered(self):
        """Enter starts a download, or queues the link while one is running."""
        if not self._is_downloading:
            self.on_returnButton()
            return
        links = self.PlaylistLink.text().split()
        if not links:
            return
        if self._cancel_event.is_set():
            self.statusMsg.setText(t("status.stopping_no_queue"))
            return
        bad = self._invalid_links(links)
        if bad:
            self.statusMsg.setText(t("status.not_spotify", link=bad[0]))
            return
        new = [u for u in dict.fromkeys(links) if u != self._current_link and u not in self._queue]
        self._queue.extend(new)
        self.PlaylistLink.clear()
        self.statusMsg.setText(
            t("status.queued", new=len(new), waiting=len(self._queue))
            if new
            else t("status.already_queued")
        )
        self._update_queue_hint()

    def _take_links(self, text: str) -> None:
        """Links from the clipboard, a drop, or history: queue them, or line them up."""
        links = [u for u in (text or "").split() if not self._invalid_links([u])]
        if not links:
            self.statusMsg.setText(t("status.no_link_found"))
            return
        self.PlaylistLink.setText(" ".join(dict.fromkeys(links)))
        if self._is_downloading:
            self._on_link_entered()
            return
        self.PlaylistLink.setFocus()
        self.statusMsg.setText(t("status.link_ready"))

    def _paste_from_clipboard(self):
        clipboard = QApplication.clipboard()
        self._take_links(clipboard.text() if clipboard is not None else "")

    def dragEnterEvent(self, event):
        mime = event.mimeData()
        if mime.hasText() or mime.hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        mime = event.mimeData()
        text = mime.text() or " ".join(u.toString() for u in mime.urls())
        event.acceptProposedAction()
        self._take_links(text)

    def _update_queue_hint(self):
        if not self._is_downloading:
            hint = self._idle_placeholder
        elif self._queue:
            hint = t("hint.queued", count=len(self._queue))
        else:
            hint = t("hint.queue_more")
        self.PlaylistLink.setPlaceholderText(hint)

    def _set_downloading(self, active: bool) -> None:
        self._is_downloading = active
        self.DownloadBtn.setText(t("main.stop") if active else t("main.download"))
        self.DownloadBtn.setProperty("stopping", active)
        style = self.DownloadBtn.style()
        if style is not None:  # re-read the [stopping] stylesheet rule
            style.unpolish(self.DownloadBtn)
            style.polish(self.DownloadBtn)

    def _start_download(self, spotify_url: str):
        try:
            # Validate URL type
            url_type, _ = detect_spotify_url_type(spotify_url)
            self.statusMsg.setText(t("status.detected", kind=t(f"kind.{url_type}")))

            # Reset cancel event and set downloading state
            self._cancel_event = threading.Event()
            self._current_link = spotify_url
            self._started_at = time.time()
            self.PlaylistLink.clear()
            self._set_downloading(True)
            self.SongDownloadprogress.setValue(0)
            self.CounterLabel.setText(t("main.counter", done=0))

            self.scraper_thread = engine.ScraperThread(
                spotify_url,
                self.download_path,
                cancel_event=self._cancel_event,
                **config.scraper_kwargs_from(self._config),
            )
            self.scraper_thread.progress_update.connect(self.update_progress)
            self.scraper_thread.finished.connect(self.thread_finished)
            self.scraper_thread.scraper.song_Album.connect(self.update_AlbumName)
            self.scraper_thread.scraper.song_meta.connect(self.update_song_META)
            self.scraper_thread.scraper.add_song_meta.connect(self.add_song_META)
            self.scraper_thread.scraper.dlprogress_signal.connect(self.update_song_progress)
            self.scraper_thread.scraper.Resetprogress_signal.connect(self.Reset_song_progress)
            self.scraper_thread.scraper.PlaylistCompleted.connect(self.statusMsg.setText)
            self.scraper_thread.scraper.error_signal.connect(self.statusMsg.setText)

            # Connect the count_updated signal to the update_counter slot
            self.scraper_thread.scraper.count_updated.connect(self.update_counter)
            # after update_counter so the label reads "1" before the prompt opens
            self.scraper_thread.scraper.count_updated.connect(self._maybe_show_star_prompt)

            self.scraper_thread.start()
            self._update_queue_hint()

        except ValueError as e:
            self.statusMsg.setText(str(e))
            self._set_downloading(False)

    def _stop_download(self):
        """Stop the current download gracefully using cooperative cancellation."""
        dropped = len(self._queue)
        self._queue.clear()
        self.statusMsg.setText(
            t("status.stopping_cleared", count=dropped) if dropped else t("status.stopping")
        )
        self.DownloadBtn.setEnabled(False)

        # Signal cancellation via event (thread checks this periodically)
        self._cancel_event.set()

        if hasattr(self, "scraper_thread") and self.scraper_thread.isRunning():
            self.scraper_thread.request_cancel()
            # Thread will finish current track and exit; UI resets via thread_finished signal

    def _run_outcome(self) -> dict:
        """What the run that just ended did, read defensively off its scraper."""
        scraper = self._live_scraper()
        folder = getattr(scraper, "output_folder", None)
        name = getattr(scraper, "display_name", "")
        failed = getattr(scraper, "_failed_tracks", None)
        counter = getattr(scraper, "counter", 0)
        failed_n = len(failed) if isinstance(failed, list) else 0
        finished = counter if isinstance(counter, int) else 0
        return {
            "folder": folder if isinstance(folder, str) else "",
            "name": name if isinstance(name, str) else "",
            "landed": max(0, finished - failed_n),
            "failed": failed_n,
        }

    def thread_finished(self):
        """Reset UI state when download thread finishes."""
        link, outcome = self._current_link, self._run_outcome()
        stopped = self._cancel_event.is_set()
        if link:
            if outcome["folder"]:
                self._last_folder = outcome["folder"]
            try:
                kind = detect_spotify_url_type(link)[0]
            except ValueError:
                kind = "unknown"
            history.record(
                url=link,
                kind=kind,
                name=outcome["name"] or link,
                folder=outcome["folder"],
                started_at=self._started_at or None,
                landed=outcome["landed"],
                failed=outcome["failed"],
                stopped=stopped,
            )
        self._current_link = ""
        self._set_downloading(False)
        self.DownloadBtn.setEnabled(True)
        if hasattr(self, "scraper_thread"):
            self.scraper_thread.deleteLater()  # Clean up the thread properly
        if self._queue and not stopped:
            self._start_download(self._queue.popleft())
        elif link and not stopped:
            self._notify_finished(outcome["name"] or link, outcome["landed"], outcome["failed"])
        self._update_queue_hint()

    # ---- progress -------------------------------------------------------

    def update_progress(self, message):
        self.statusMsg.setText(message)

    @pyqtSlot(dict)
    def update_song_META(self, song_meta):
        """Update UI with current track info (called BEFORE download starts)."""
        if self.showPreviewCheck.isChecked():
            cover_url = song_meta.get("cover", "")
            if cover_url:
                thumb_thread = DownloadThumbnail(cover_url, self)
                self._active_threads.append(thumb_thread)
                thumb_thread.finished.connect(lambda: self._cleanup_thread(thumb_thread))
                thumb_thread.start()
            artists_full = song_meta.get("artists", "")
            artist_list = [a.strip() for a in artists_full.split(",") if a.strip()]
            if len(artist_list) > 2:
                artists_display = f"{artist_list[0]}, {artist_list[1]} +{len(artist_list) - 2}"
            else:
                artists_display = artists_full
            self.ArtistNameText.setText(artists_display)
            self.ArtistNameText.setToolTip(dialogs.plain_tooltip(artists_full))
            self.AlbumText.setText(song_meta.get("album", "") or "—")
            self.SongName.setText(song_meta.get("title", ""))
            self.YearText.setText((song_meta.get("releaseDate", "") or "—")[:10])

        title, artists = song_meta.get("title", ""), song_meta.get("artists", "")
        self.MainSongName.setText(f"{title} - {artists}" if artists else title)
        self.MainSongName.setToolTip(dialogs.plain_tooltip(self.MainSongName.text()))
        # NOTE: Meta tags are written in add_song_META (after file exists), not here

    @pyqtSlot(dict)
    def add_song_META(self, song_meta):
        if self.AddMetaDataCheck.isChecked():
            meta_thread = tagging.WritingMetaTagsThread(song_meta, song_meta["file"])
            meta_thread.tags_success.connect(self.statusMsg.setText)
            self._active_threads.append(meta_thread)
            meta_thread.finished.connect(lambda: self._cleanup_thread(meta_thread))
            meta_thread.start()

    def _cleanup_thread(self, thread):
        """Remove finished thread from active list."""
        if thread in self._active_threads:
            self._active_threads.remove(thread)

    @pyqtSlot(str)
    def update_AlbumName(self, AlbumName):
        self.AlbumName.setText(t("main.playlist", name=AlbumName))
        self.AlbumName.setToolTip(dialogs.plain_tooltip(AlbumName))

    def _live_scraper(self):
        """The running scraper, or None once the thread is gone (qt raises
        RuntimeError on a deleted object, which outlives the python ref)."""
        try:
            return getattr(getattr(self, "scraper_thread", None), "scraper", None)
        except RuntimeError:
            return None

    def _failed_track_count(self) -> int:
        return len(getattr(self._live_scraper(), "_failed_tracks", []) or [])

    @pyqtSlot(int)
    def update_counter(self, count):
        scraper = self._live_scraper()
        total = getattr(scraper, "_total_tracks", 0) or 0
        failed = self._failed_track_count()
        # count is "tracks finished", not "tracks saved": a failure ticks it too
        text = t("main.counter", done=max(0, count - failed))
        if total:
            text += t("main.counter.of", total=total)
        if failed:
            text += t("main.counter.failed", failed=failed)
        self.CounterLabel.setText(text)

    @pyqtSlot(int)
    def update_song_progress(self, progress):
        self.SongDownloadprogressBar.setValue(progress)
        self.SongDownloadprogress.setValue(progress)

    @pyqtSlot(int)
    def Reset_song_progress(self, progress):
        self.SongDownloadprogressBar.setValue(0)
        self.SongDownloadprogress.setValue(0)

    # ---- frameless window behaviour ---------------------------------------

    # DRAGGLESS INTERFACE
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.m_drag = True
            self.m_DragPosition = event.globalPosition().toPoint() - self.pos()
            event.accept()
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))

    def mouseMoveEvent(self, QMouseEvent):
        try:
            if Qt.MouseButton.LeftButton and self.m_drag:
                self.move(QMouseEvent.globalPosition().toPoint() - self.m_DragPosition)
                QMouseEvent.accept()
        except AttributeError:
            pass

    def mouseReleaseEvent(self, QMouseEvent):
        self.m_drag = False
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    def _animate_panel(self, width: int, duration: int):
        self.animation = QPropertyAnimation(self.SONGINFORMATION, b"size")
        self.animation.setDuration(duration)
        self.animation.setEndValue(QSize(width, _PANEL_H))
        self.animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.animation.start()

    def CloseSongInformation(self):
        self._animate_panel(0, 250)

    def OpenSongInformation(self):
        self._animate_panel(_PANEL_OPEN_W, 450)

    def show_preview(self, state):
        checked = state == Qt.CheckState.Checked.value or state is True
        if checked:
            self.OpenSongInformation()
        else:
            self.CloseSongInformation()
        if self._config.get("show_preview") != checked:
            self._config["show_preview"] = checked
            config.save_config(self._config)

    def restore_preview(self):
        """Open the panel at launch, without the slide, when it was left open."""
        if self._config.get("show_preview"):
            self.showPreviewCheck.blockSignals(True)
            self.showPreviewCheck.setChecked(True)
            self.showPreviewCheck.blockSignals(False)
            self.SONGINFORMATION.resize(_PANEL_OPEN_W, _PANEL_H)

    def exitprogram(self):
        # QApplication.quit() unwinds the event loop cleanly so app.exec()
        # returns and the atexit session-end runs; sys.exit() inside a slot
        # raised SystemExit into qt's excepthook and logged a false crash
        QApplication.quit()

    def Linkedin(self):
        webbrowser.open("https://www.linkedin.com/in/sunny-patel-30b460204/")
