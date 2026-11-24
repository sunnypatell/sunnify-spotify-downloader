"""The desktop app's dialogs: settings, history, and the two one-card toasts."""

from __future__ import annotations

import contextlib
import html
import os
import time

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import (
    QColor,
    QCursor,
    QDesktopServices,
    QFont,
    QFontMetrics,
    QStandardItemModel,
)
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from sunnify import history, logs
from sunnify.config import (
    SUPPORTED_FORMATS,
    SUPPORTED_LANGUAGES,
    SUPPORTED_QUALITIES,
    SUPPORTED_SAMPLE_RATES,
    SUPPORTED_THEMES,
    SUPPORTED_UI_SCALES,
)
from sunnify.gui import scale, theme
from sunnify.i18n import t
from sunnify.logs import log
from sunnify.updates import GITHUB_REPO


def plain_tooltip(text: str) -> str:
    """A tooltip that shows text exactly as typed.

    Qt renders a tooltip as HTML whenever it looks like markup, and playlist
    names, titles and paths are other people's text: a playlist called
    "<h1>Free</h1>" must read as that, not render as a banner."""
    if not text:
        return ""
    return f"<p style='white-space:pre-wrap'>{html.escape(text)}</p>"


def plain_text_labels(root: QWidget) -> None:
    """Every QLabel under root shows its text literally, never as HTML.

    QLabel's default AutoText format renders anything that looks like markup,
    and these labels show playlist names, song titles and messages built from
    them. Nothing in the app relies on rich text, so none is allowed."""
    for label in root.findChildren(QLabel):
        label.setTextFormat(Qt.TextFormat.PlainText)


def _open_url(url: str) -> bool:
    """Hand an https URL to the OS browser; anything else is refused and logged."""
    if not url.startswith("https://"):
        log.warning("refused to open a non-https url: %r", url)
        return False
    ok = QDesktopServices.openUrl(QUrl(url))
    if not ok:
        log.warning("could not open in the browser: %s", url)
    return ok


def open_folder(path: str, *, create: bool = False) -> bool:
    """Reveal a folder in the OS file manager.

    Only ever a directory: the path can come from config.json or history.json,
    and handing a file to the OS opener would launch it."""
    if not path:
        return False
    if create:
        with contextlib.suppress(OSError):
            os.makedirs(path, exist_ok=True)
    if not os.path.isdir(path):
        log.warning("not opening %r: not a folder", path)
        return False
    ok = QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(path)))
    if not ok:
        log.warning("could not open folder: %s", path)
    return ok


class SettingsDialog(QDialog):
    """Every setting, grouped into sections; scrolls when the screen is small."""

    # filename styles: the stored value pair behind each pick-one entry
    _STYLES = ("song_artist", "artist_song", "song_only")

    def __init__(self, parent, config: dict):
        super().__init__(parent)
        self.setWindowTitle(t("settings.title"))
        self.setModal(True)
        # min width so long macOS paths fit; height is sized at the end once hints exist
        self.setMinimumWidth(560)
        self._config = dict(config)

        # Read-only QLineEdit: long paths scroll instead of truncating;
        # tooltip carries the full value.
        self._folder_label = QLineEdit(self._config.get("download_path") or t("settings.not_set"))
        self._folder_label.setReadOnly(True)
        self._folder_label.setCursorPosition(0)
        self._folder_label.setToolTip(plain_tooltip(self._folder_label.text()))
        browse = QPushButton(t("settings.choose_folder"))
        browse.clicked.connect(self._choose_folder)
        folder_row = QHBoxLayout()
        folder_row.setSpacing(8)
        folder_row.addWidget(self._folder_label, 1)
        folder_row.addWidget(browse)

        self._format_cb = QComboBox()
        for key in SUPPORTED_FORMATS:
            self._format_cb.addItem(key)
        self._format_cb.setCurrentText(self._config.get("format", "mp3"))
        self._format_cb.currentTextChanged.connect(self._on_format_change)

        self._quality_cb = QComboBox()
        for q in SUPPORTED_QUALITIES:
            self._quality_cb.addItem(f"{q} kbps")
        self._quality_cb.setCurrentText(f"{self._config.get('quality', '192')} kbps")

        # display text <-> stored value; stored value is what ffmpeg -ar gets
        self._sample_rate_labels = {
            "auto": t("settings.sample_rate.auto"),
            "44100": "44.1 kHz",
            "48000": "48 kHz",
        }
        self._sample_rate_cb = QComboBox()
        for value in SUPPORTED_SAMPLE_RATES:
            self._sample_rate_cb.addItem(self._sample_rate_labels[value], value)
        current_sr = self._config.get("sample_rate", "auto")
        self._sample_rate_cb.setCurrentIndex(
            SUPPORTED_SAMPLE_RATES.index(current_sr) if current_sr in SUPPORTED_SAMPLE_RATES else 0
        )

        self._include_track_number_cb = QCheckBox()
        self._include_track_number_cb.setChecked(self._config.get("include_track_number", False))

        # the three naming shapes are mutually exclusive, so they present as
        # one pick-one control; underneath they map to the artist_first and
        # title_only config booleans the engine and CLI flags already use
        self._filename_style_cb = QComboBox()
        for style in self._STYLES:
            self._filename_style_cb.addItem(t(f"settings.style.{style}"), style)
        if self._config.get("title_only", False):
            self._filename_style_cb.setCurrentIndex(2)
        elif self._config.get("artist_first", False):
            self._filename_style_cb.setCurrentIndex(1)

        self._filename_preview = QLabel()
        self._filename_preview.setStyleSheet("font-weight: 700;")
        self._include_track_number_cb.toggled.connect(self._update_filename_preview)
        self._filename_style_cb.currentIndexChanged.connect(self._update_filename_preview)
        self._format_cb.currentTextChanged.connect(self._update_filename_preview)

        self._loose_match_cb = QCheckBox()
        self._loose_match_cb.setChecked(self._config.get("loose_match", False))
        self._lyrics_cb = QCheckBox()
        self._lyrics_cb.setChecked(self._config.get("lyrics", False))
        self._notify_cb = QCheckBox()
        self._notify_cb.setChecked(self._config.get("notify", True))

        self._language_cb = QComboBox()
        for value in SUPPORTED_LANGUAGES:
            self._language_cb.addItem(t(f"settings.language.{value}"), value)
        lang = self._config.get("language", "auto")
        self._language_cb.setCurrentIndex(
            SUPPORTED_LANGUAGES.index(lang) if lang in SUPPORTED_LANGUAGES else 0
        )

        self._theme_cb = QComboBox()
        for value in SUPPORTED_THEMES:
            self._theme_cb.addItem(t(f"settings.theme.{value}"), value)
        th = self._config.get("theme", "system")
        self._theme_cb.setCurrentIndex(SUPPORTED_THEMES.index(th) if th in SUPPORTED_THEMES else 0)

        self._ui_scale_labels = {value: f"{value}%" for value in SUPPORTED_UI_SCALES}
        self._ui_scale_cb = QComboBox()
        for value in SUPPORTED_UI_SCALES:
            self._ui_scale_cb.addItem(self._ui_scale_labels[value])
        current_scale = self._config.get("ui_scale", "100")
        if current_scale not in SUPPORTED_UI_SCALES:
            current_scale = "100"
        self._ui_scale_cb.setCurrentText(self._ui_scale_labels[current_scale])
        self._disable_scales_larger_than_screen()

        # initial enable/disable sync needs every dependent combo to exist
        self._on_format_change(self._format_cb.currentText())
        self._update_filename_preview()

        sections: list[tuple[str, list[tuple[str, QWidget | QHBoxLayout, str]]]] = [
            (
                t("settings.section.downloads"),
                [
                    (t("settings.folder"), folder_row, t("settings.folder.hint")),
                    (t("settings.format"), self._format_cb, t("settings.format.hint")),
                    (t("settings.quality"), self._quality_cb, t("settings.quality.hint")),
                    (
                        t("settings.sample_rate"),
                        self._sample_rate_cb,
                        t("settings.sample_rate.hint"),
                    ),
                ],
            ),
            (
                t("settings.section.names"),
                [
                    (
                        t("settings.style"),
                        self._filename_style_cb,
                        t("settings.style.hint"),
                    ),
                    (
                        t("settings.track_number"),
                        self._include_track_number_cb,
                        t("settings.track_number.hint"),
                    ),
                    (t("settings.preview"), self._filename_preview, ""),
                ],
            ),
            (
                t("settings.section.matching"),
                [
                    (
                        t("settings.loose_match"),
                        self._loose_match_cb,
                        t("settings.loose_match.hint"),
                    ),
                    (t("settings.lyrics"), self._lyrics_cb, t("settings.lyrics.hint")),
                ],
            ),
            (
                t("settings.section.app"),
                [
                    (t("settings.language"), self._language_cb, t("settings.language.hint")),
                    (t("settings.theme"), self._theme_cb, ""),
                    (t("settings.ui_scale"), self._ui_scale_cb, t("settings.ui_scale.hint")),
                    (t("settings.notify"), self._notify_cb, t("settings.notify.hint")),
                ],
            ),
        ]
        # one label column across sections, measured from the longest label
        fm = QFontMetrics(self.font())
        label_w = max(fm.horizontalAdvance(lbl) for _, rows in sections for lbl, _, _ in rows) + 12

        rows_host = QWidget()
        rows = QVBoxLayout(rows_host)
        rows.setSpacing(14)
        rows.setContentsMargins(4, 4, 8, 4)
        for title, entries in sections:
            rows.addWidget(self._section(title, entries, label_w))
        rows.addStretch(1)

        # settings scroll when the screen can't fit them (small laptops,
        # windows dpi scaling); the button row never leaves the screen
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setWidget(rows_host)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        for which, text in (
            (QDialogButtonBox.StandardButton.Ok, t("settings.save")),
            (QDialogButtonBox.StandardButton.Cancel, t("common.cancel")),
        ):
            button = btns.button(which)
            if button is not None:
                button.setText(text)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        # one click to the log file a bug report needs, without hunting for it
        open_logs = QPushButton(t("settings.open_logs"))
        open_logs.setToolTip(plain_tooltip(logs.log_file_path()))
        open_logs.clicked.connect(self._open_logs)
        btns.addButton(open_logs, QDialogButtonBox.ButtonRole.ActionRole)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 14)
        layout.setSpacing(12)
        layout.addWidget(self._scroll, 1)
        layout.addWidget(btns)

        # activate() first: hint labels word-wrap, so their heights are
        # height-for-width and only correct after layout activation. Then
        # open at the content's natural size, clamped to the screen so small
        # laptops and dpi scaling scroll instead of clipping.
        rows.activate()
        layout.activate()
        content_w = max(rows_host.sizeHint().width() + 48, 640)
        content_h = (
            rows.totalHeightForWidth(rows_host.sizeHint().width()) + btns.sizeHint().height() + 56
        )
        screen = self.screen() or QApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            content_w = min(content_w, int(avail.width() * 0.9))
            content_h = min(content_h, int(avail.height() * 0.9))
        self.resize(content_w, content_h)
        plain_text_labels(self)

    @staticmethod
    def _section(title: str, entries, label_w: int) -> QFrame:
        """A titled card of rows: label + control, the hint wrapped under the control."""
        frame = QFrame()
        frame.setObjectName("settingsSection")
        box = QVBoxLayout(frame)
        box.setContentsMargins(16, 12, 16, 14)
        box.setSpacing(10)
        heading = QLabel(title.upper())
        heading.setObjectName("sectionTitle")
        box.addWidget(heading)
        for label_text, control, hint_text in entries:
            block = QVBoxLayout()
            block.setSpacing(3)
            row = QHBoxLayout()
            row.setSpacing(12)
            name = QLabel(label_text)
            name.setFixedWidth(label_w)
            name.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row.addWidget(name)
            if isinstance(control, QHBoxLayout):
                row.addLayout(control, 1)
            else:
                row.addWidget(control, 1)
            block.addLayout(row)
            if hint_text:
                hint = QLabel(hint_text)
                hint.setObjectName("hint")
                hint.setWordWrap(True)
                hint.setContentsMargins(label_w + 12, 0, 4, 0)
                hint.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
                block.addWidget(hint)
            box.addLayout(block)
        return frame

    def _open_logs(self):
        open_folder(logs._log_dir(), create=True)

    def _choose_folder(self):
        start = (
            self._folder_label.text()
            if os.path.isdir(self._folder_label.text())
            else os.path.expanduser("~")
        )
        folder = QFileDialog.getExistingDirectory(
            self,
            t("settings.choose_folder.title"),
            start,
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks,
        )
        if folder:
            chosen = with_sunnify_subfolder(folder)
            self._folder_label.setText(chosen)
            self._folder_label.setCursorPosition(0)
            self._folder_label.setToolTip(plain_tooltip(chosen))

    def _on_format_change(self, fmt: str) -> None:
        """Lossless formats (flac/wav) ignore the bitrate selector. The
        sample-rate selector only applies to formats that always transcode
        (mp3/flac/wav): opus is 48 kHz-only and m4a may stream-copy."""
        is_lossy = bool(SUPPORTED_FORMATS.get(fmt, {}).get("lossy", True))
        self._quality_cb.setEnabled(is_lossy)
        self._sample_rate_cb.setEnabled(fmt in ("mp3", "flac", "wav"))

    def _disable_scales_larger_than_screen(self) -> None:
        """Grey out sizes at which the window would not fit this screen.

        The window is WINDOW_W x WINDOW_H at the factor in effect now, so a
        candidate size changes it in proportion to that factor."""
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return
        avail = screen.availableGeometry()
        current = scale._current_ui_factor()
        model = self._ui_scale_cb.model()
        if not isinstance(model, QStandardItemModel):  # a plain QComboBox always has one
            return
        for i, value in enumerate(SUPPORTED_UI_SCALES):
            factor = int(value) / 100 / current
            fits = (
                scale.WINDOW_W * factor <= avail.width()
                and scale.WINDOW_H * factor <= avail.height()
            )
            item = model.item(i)
            if item is not None:
                item.setEnabled(fits)

    def _update_filename_preview(self, *_args) -> None:
        style = self._filename_style_cb.currentData() or "song_artist"
        song, artist = t("settings.preview.song"), t("settings.preview.artist")
        stem = {
            "song_artist": f"{song} - {artist}",
            "artist_song": f"{artist} - {song}",
            "song_only": song,
        }[style]
        prefix = "01. " if self._include_track_number_cb.isChecked() else ""
        ext = SUPPORTED_FORMATS.get(self._format_cb.currentText(), {"ext": "mp3"})["ext"]
        self._filename_preview.setText(f"{prefix}{stem}.{ext}")

    def result_config(self) -> dict:
        folder = self._folder_label.text()
        if folder != t("settings.not_set"):
            self._config["download_path"] = folder
        self._config["format"] = self._format_cb.currentText()
        self._config["quality"] = self._quality_cb.currentText().split()[0]
        self._config["include_track_number"] = self._include_track_number_cb.isChecked()
        style = self._filename_style_cb.currentData()
        self._config["title_only"] = style == "song_only"
        if style == "song_only":
            # keep the stored order preference so switching back remembers it
            self._config.setdefault("artist_first", False)
        else:
            self._config["artist_first"] = style == "artist_song"
        self._config["sample_rate"] = self._sample_rate_cb.currentData() or "auto"
        self._config["loose_match"] = self._loose_match_cb.isChecked()
        self._config["lyrics"] = self._lyrics_cb.isChecked()
        self._config["notify"] = self._notify_cb.isChecked()
        self._config["language"] = self._language_cb.currentData() or "auto"
        self._config["theme"] = self._theme_cb.currentData() or "system"
        scale_label_to_value = {v: k for k, v in self._ui_scale_labels.items()}
        self._config["ui_scale"] = scale_label_to_value.get(self._ui_scale_cb.currentText(), "100")
        return self._config


def with_sunnify_subfolder(folder: str) -> str:
    """Keep downloads in a "Sunnify" folder, without nesting Sunnify/Sunnify."""
    if os.path.basename(folder.rstrip("/\\")) == "Sunnify":
        return folder
    return os.path.join(folder, "Sunnify")


class _ToastCard(QDialog):
    """A frameless, centred card: brand header, one message, a ghost and a primary button."""

    _url = ""  # where the primary button goes; each card sets its own

    def __init__(self, parent, *, eyebrow, heading, body, subheading=None, dismiss, action):
        super().__init__(parent)
        p = theme.current()
        self.setWindowTitle(heading)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setModal(True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 26, 28, 30)  # room for the drop shadow
        # fractional dpi under-measures the wrapped body and squeezes the card (#64)
        outer.setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)

        card = QFrame()
        card.setObjectName("card")
        card.setFixedWidth(430)
        card.setStyleSheet(
            f"QFrame#card{{background:{p.window};border:1px solid {p.border};border-radius:18px;}}"
        )
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(48)
        shadow.setOffset(0, 16)
        shadow.setColor(QColor(*p.shadow))
        card.setGraphicsEffect(shadow)
        outer.addWidget(card)

        v = QVBoxLayout(card)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        header = QFrame()
        header.setObjectName("hdr")
        header.setStyleSheet(
            "QFrame#hdr{border-top-left-radius:18px;border-top-right-radius:18px;"
            f"background:{theme.BRAND_GRADIENT};}}"
        )
        hv = QVBoxLayout(header)
        hv.setContentsMargins(26, 20, 26, 22)
        hv.setSpacing(0)  # gaps are set explicitly between rows below

        eyebrow_lbl = QLabel(eyebrow)
        ef = QFont(self.font())
        ef.setPointSizeF(max(ef.pointSizeF(), 8) * 0.9)
        ef.setBold(True)
        ef.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.5)
        eyebrow_lbl.setFont(ef)
        eyebrow_lbl.setStyleSheet("color: rgba(255,255,255,0.85); background: transparent;")
        hv.addWidget(eyebrow_lbl)
        hv.addSpacing(8)

        name = QLabel(heading)
        nfont = QFont(self.font())
        nfont.setPointSize(20)
        nfont.setBold(True)
        name.setFont(nfont)
        name.setStyleSheet("color: #FFFFFF; background: transparent;")
        # large bold glyphs exceed QLabel's tight default box; reserve full height
        name.setMinimumHeight(QFontMetrics(nfont).height() + 10)
        hv.addWidget(name)
        if subheading:
            hv.addSpacing(10)  # clear gap so a descender never crowds the line below
            sub = QLabel(subheading)
            sfont = QFont(self.font())
            sfont.setPointSize(12)
            sub.setFont(sfont)
            sub.setStyleSheet("color: #FFFFFF; background: transparent;")
            sub.setMinimumHeight(QFontMetrics(sfont).height() + 6)
            hv.addWidget(sub)
        else:
            hv.addSpacing(6)  # descender room; 'j'/'y'/'g' tails clip at 1.5x without it
        v.addWidget(header)

        body_host = QWidget()
        bv = QVBoxLayout(body_host)
        bv.setContentsMargins(26, 22, 26, 6)
        msg = QLabel(body)
        msg.setWordWrap(True)
        msg.setStyleSheet(f"color: {p.muted}; background: transparent;")
        bv.addWidget(msg)
        v.addWidget(body_host)

        footer = QWidget()
        fv = QHBoxLayout(footer)
        fv.setContentsMargins(26, 8, 26, 22)
        fv.setSpacing(10)

        bold = QFont(self.font())
        bold.setBold(True)
        later = QPushButton(dismiss)
        later.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        later.setFont(bold)
        later.setFixedHeight(40)
        # pad right so the invisible hit area is as big as it looks
        later.setStyleSheet(
            f"QPushButton{{background:transparent;color:{p.muted};border:none;"
            "text-align:left;padding-right:32px;}"
            f"QPushButton:hover{{color:{p.text};}}"
        )
        later.clicked.connect(self.reject)
        fv.addWidget(later)
        fv.addStretch(1)

        cta = QPushButton(action)
        cta.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        cta.setFont(bold)
        cta.setFixedHeight(40)
        # metrics-derived width; a fixed box clips when linux substitutes the font
        cta.setMinimumWidth(QFontMetrics(bold).horizontalAdvance(action) + 44)
        cta.setStyleSheet(
            f"QPushButton{{background:{p.accent};color:{p.accent_text};border:none;"
            "border-radius:10px;padding-left:18px;padding-right:18px;}"
            f"QPushButton:hover{{background:{p.accent_hover};}}"
        )
        cta.clicked.connect(self._on_action)
        fv.addWidget(cta)
        v.addWidget(footer)
        plain_text_labels(self)

    def _on_action(self):
        _open_url(self._url)
        self.accept()


class UpdateNotifier(_ToastCard):
    """'New version available'. Download opens the releases page, where the notes live."""

    def __init__(self, parent, current: str, latest: str, url: str):
        super().__init__(
            parent,
            eyebrow=t("update.eyebrow"),
            heading="Sunnify",
            subheading=f"{current}  →  {latest}",
            body=t("update.body"),
            dismiss=t("update.later"),
            action=t("update.download"),
        )
        self._url = url


class StarPromptNotifier(_ToastCard):
    """One-time 'star the repo' card, shown the moment the first song of the
    user's first download lands on disk (owner call: value is proven by a
    real file and the user is mid-wait; huge playlists never reach
    'complete' in one sitting, so completion was the wrong hook). Shown
    exactly once per install: the config flag is persisted before the dialog
    opens, so even a crash mid-dialog can never make it nag twice."""

    def __init__(self, parent):
        super().__init__(
            parent,
            eyebrow=t("star.eyebrow"),
            heading=t("star.heading"),
            body=t("star.body"),
            dismiss=t("star.later"),
            action=t("star.action"),
        )
        self._url = f"https://github.com/{GITHUB_REPO}"


class HistoryDialog(QDialog):
    """Past downloads, newest first: open the folder, or download the link again."""

    def __init__(self, parent, entries: list[dict] | None = None):
        super().__init__(parent)
        self.setWindowTitle(t("history.title"))
        self.setModal(True)
        self.setMinimumSize(520, 420)
        self.requested_url: str | None = None
        self._entries = list(entries if entries is not None else history.load())

        heading = QLabel(t("history.title"))
        hfont = QFont(self.font())
        hfont.setPointSize(15)
        hfont.setBold(True)
        heading.setFont(hfont)
        sub = QLabel(t("history.subtitle"))
        sub.setObjectName("hint")
        sub.setWordWrap(True)

        self._list = QListWidget()
        self._list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self._list.itemDoubleClicked.connect(lambda _item: self._open_selected())
        self._list.currentRowChanged.connect(self._sync_buttons)
        self._empty = QLabel(t("history.empty"))
        self._empty.setObjectName("hint")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._open_btn = QPushButton(t("history.open_folder"))
        self._open_btn.clicked.connect(self._open_selected)
        self._again_btn = QPushButton(t("history.again"))
        self._again_btn.setProperty("primary", True)
        self._again_btn.clicked.connect(self._again_selected)
        self._clear_btn = QPushButton(t("history.clear"))
        self._clear_btn.clicked.connect(self._clear)
        close = QPushButton(t("common.close"))
        close.clicked.connect(self.reject)

        # Enter downloads again; it must never be the button that wipes history
        for btn in (self._open_btn, self._clear_btn, close):
            btn.setAutoDefault(False)
        self._again_btn.setDefault(True)

        buttons = QHBoxLayout()
        buttons.addWidget(self._clear_btn)
        buttons.addStretch(1)
        buttons.addWidget(self._open_btn)
        buttons.addWidget(self._again_btn)
        buttons.addWidget(close)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 14)
        layout.setSpacing(10)
        layout.addWidget(heading)
        layout.addWidget(sub)
        layout.addWidget(self._list, 1)
        layout.addWidget(self._empty, 1)
        layout.addLayout(buttons)
        plain_text_labels(self)
        self._populate()

    @staticmethod
    def describe(entry: dict) -> str:
        """Two lines: what it was, then when, how it went, how many landed."""
        when = entry.get("finished_at") or entry.get("started_at") or 0
        stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(when)) if when else "?"
        status = entry.get("status", "done")
        parts = [stamp, t(f"history.status.{status}")]
        parts.append(t("history.counts", landed=entry.get("landed", 0)))
        if entry.get("failed"):
            parts.append(t("history.failed", failed=entry["failed"]))
        name = entry.get("name") or entry.get("url", "")
        return f"{name}\n" + "  ·  ".join(parts)

    def _populate(self):
        self._list.clear()
        for entry in self._entries:
            item = QListWidgetItem(self.describe(entry))
            item.setToolTip(plain_tooltip(f"{entry.get('url', '')}\n{entry.get('folder', '')}"))
            self._list.addItem(item)
        has = bool(self._entries)
        self._list.setVisible(has)
        self._empty.setVisible(not has)
        self._clear_btn.setEnabled(has)
        if has:
            self._list.setCurrentRow(0)
        self._sync_buttons()

    def _selected(self) -> dict | None:
        row = self._list.currentRow()
        return self._entries[row] if 0 <= row < len(self._entries) else None

    def _sync_buttons(self, *_args):
        entry = self._selected()
        self._open_btn.setEnabled(bool(entry and os.path.isdir(entry.get("folder") or "")))
        self._again_btn.setEnabled(bool(entry and entry.get("url")))

    def _open_selected(self):
        entry = self._selected()
        if entry and entry.get("folder"):
            open_folder(entry["folder"])

    def _again_selected(self):
        entry = self._selected()
        if entry and entry.get("url"):
            self.requested_url = entry["url"]
            self.accept()

    def _clear(self):
        history.clear()
        self._entries = []
        self._populate()
