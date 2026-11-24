"""Colour tokens and the stylesheets built from them.

Every colour the desktop app paints comes from a Palette here, so dark and light
stay one design. Text pairs were picked for contrast: body text and muted text
clear WCAG AA on their backgrounds in both themes, and the green accent carries
dark text, which reads on it in both (white on Spotify green does not).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from sunnify.logs import log


@dataclass(frozen=True)
class Palette:
    name: str
    window: str  # the cards
    surface: str  # panels inset into a card
    surface_hover: str
    border: str
    input_bg: str
    text: str
    muted: str
    accent: str  # fills: the download button, progress
    accent_hover: str
    accent_pressed: str
    accent_text: str  # text on an accent fill
    accent_ink: str  # accent-coloured text on a card
    danger: str
    danger_text: str  # text on a danger fill
    shadow: tuple  # rgba of the card drop shadow


DARK = Palette(
    name="dark",
    window="#141417",
    surface="#1D1D22",
    surface_hover="#27272E",
    border="#2D2D35",
    input_bg="#0F0F12",
    text="#F3F3F6",
    muted="#A1A1AD",
    accent="#1ED760",
    accent_hover="#3BE477",
    accent_pressed="#18B04F",
    accent_text="#08130C",
    accent_ink="#1ED760",
    danger="#FF7A86",
    danger_text="#1A080B",
    shadow=(0, 0, 0, 150),
)

LIGHT = Palette(
    name="light",
    window="#FFFFFF",
    surface="#F3F4F7",
    surface_hover="#E8E9EF",
    border="#E1E2E9",
    input_bg="#FAFAFC",
    text="#15151B",
    muted="#5D5E6C",
    accent="#1ED760",
    accent_hover="#3BE477",
    accent_pressed="#18B04F",
    accent_text="#08130C",
    accent_ink="#0F7A35",
    danger="#C62F40",
    danger_text="#FFFFFF",
    shadow=(20, 10, 40, 70),
)

# the brand gradient from the original card, kept for the logo mark and toast headers
BRAND_FROM, BRAND_TO = "rgba(80, 214, 255, 255)", "rgba(112, 32, 213, 255)"
BRAND_GRADIENT = f"qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, stop:0.15 {BRAND_FROM}, stop:0.85 {BRAND_TO})"

_current = DARK
_ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")


def asset(name: str) -> str:
    """A stylesheet url() for a bundled icon; Qt wants forward slashes on every OS."""
    return os.path.join(_ASSETS, name).replace(os.sep, "/")


def current() -> Palette:
    return _current


def system_prefers_dark() -> bool:
    """The OS light/dark choice; dark when Qt can't tell (no app yet, old Qt)."""
    try:
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QGuiApplication

        hints = QGuiApplication.styleHints() if QGuiApplication.instance() else None
        if hints is None:
            return True
        return hints.colorScheme() != Qt.ColorScheme.Light
    except Exception as exc:  # pragma: no cover - Qt < 6.5
        log.debug("colour scheme not reported: %s", exc)
        return True


def resolve(setting: str | None) -> Palette:
    if setting == "light":
        return LIGHT
    if setting == "dark":
        return DARK
    return DARK if system_prefers_dark() else LIGHT


def use(setting: str | None) -> Palette:
    """Make the palette for this setting the current one and return it."""
    global _current
    _current = resolve(setting)
    return _current


def rgba(hex_color: str, alpha: float) -> str:
    """'#RRGGBB' + 0..1 alpha -> a Qt stylesheet rgba()."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r}, {g}, {b}, {int(alpha * 255)})"


def app_stylesheet(p: Palette) -> str:
    """Dialogs, menus, message boxes and every stock control the app opens."""
    return f"""
QDialog, QMessageBox {{ background: {p.window}; color: {p.text}; }}
QLabel {{ color: {p.text}; }}
QToolTip {{
    background: {p.surface}; color: {p.text}; border: 1px solid {p.border};
    border-radius: 6px; padding: 5px 8px;
}}
QPushButton {{
    background: {p.surface}; color: {p.text}; border: 1px solid {p.border};
    border-radius: 8px; padding: 7px 14px;
}}
QPushButton:hover {{ background: {p.surface_hover}; }}
QPushButton:pressed {{ background: {p.border}; }}
QPushButton:disabled {{ color: {rgba(p.muted, 0.55)}; }}
QPushButton:default, QPushButton[primary="true"] {{
    background: {p.accent}; color: {p.accent_text}; border: none; font-weight: 600;
}}
QPushButton:default:hover, QPushButton[primary="true"]:hover {{ background: {p.accent_hover}; }}
QPushButton:default:pressed, QPushButton[primary="true"]:pressed {{ background: {p.accent_pressed}; }}
QLineEdit {{
    background: {p.input_bg}; color: {p.text}; border: 1px solid {p.border};
    border-radius: 8px; padding: 6px 10px; selection-background-color: {p.accent};
    selection-color: {p.accent_text};
}}
QLineEdit:focus {{ border: 1px solid {p.accent}; }}
QComboBox {{
    background: {p.input_bg}; color: {p.text}; border: 1px solid {p.border};
    border-radius: 8px; padding: 5px 10px; min-height: 20px;
}}
QComboBox:hover {{ border: 1px solid {rgba(p.muted, 0.6)}; }}
QComboBox:disabled {{ color: {rgba(p.muted, 0.55)}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox::down-arrow {{ image: url({asset(f"chevron-{p.name}.svg")}); width: 12px; height: 12px; }}
QComboBox QAbstractItemView {{
    background: {p.window}; color: {p.text}; border: 1px solid {p.border};
    selection-background-color: {p.surface_hover}; selection-color: {p.text}; outline: 0;
}}
QCheckBox {{ color: {p.text}; spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px; border-radius: 5px;
    border: 1px solid {rgba(p.muted, 0.7)}; background: {p.input_bg};
}}
QCheckBox::indicator:hover {{ border: 1px solid {p.accent}; }}
QCheckBox::indicator:checked {{
    background: {p.accent}; border: 1px solid {p.accent}; image: url({asset("check.svg")});
}}
QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {p.border}; border-radius: 4px; min-height: 28px; }}
QScrollBar::handle:vertical:hover {{ background: {rgba(p.muted, 0.6)}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QListWidget {{
    background: {p.surface}; color: {p.text}; border: 1px solid {p.border};
    border-radius: 10px; padding: 4px; outline: 0;
}}
QListWidget::item {{ border-radius: 8px; padding: 6px 8px; }}
QListWidget::item:hover {{ background: {p.surface_hover}; }}
QListWidget::item:selected {{ background: {rgba(p.accent, 0.18)}; color: {p.text}; }}
QFrame#settingsSection {{ background: {p.surface}; border-radius: 12px; }}
QLabel#sectionTitle {{
    color: {p.muted}; font-size: 11px; font-weight: 700; letter-spacing: 1px;
}}
QLabel#hint {{ color: {p.muted}; font-size: 11px; }}
"""


def window_stylesheet(p: Palette) -> str:
    """The main window's two cards and everything on them."""
    return f"""
QFrame#frame, QFrame#SONGINFORMATION {{
    background: {p.window}; border: 1px solid {p.border}; border-radius: 18px;
}}
QLabel {{ color: {p.text}; background: transparent; }}
QLabel#logo {{
    background: {BRAND_GRADIENT}; color: #FFFFFF; border-radius: 10px;
    font-size: 16px; font-weight: 800;
}}
QLabel#title {{ font-size: 18px; font-weight: 800; }}
QLabel#version {{
    color: {p.muted}; background: {p.surface}; border-radius: 8px;
    padding: 1px 7px; font-size: 10px; font-weight: 600;
}}
QLabel#author {{ color: {p.muted}; font-size: 11px; }}
QPushButton#Closed, QPushButton#SettingsBtn, QPushButton#MinimizeBtn {{
    background: transparent; color: {p.muted}; border: none; border-radius: 8px;
    font-size: 14px; padding: 0;
}}
QPushButton#SettingsBtn:hover, QPushButton#MinimizeBtn:hover {{
    background: {p.surface_hover}; color: {p.text};
}}
QPushButton#Closed:hover {{ background: {p.danger}; color: #FFFFFF; }}
QLineEdit#PlaylistLink {{
    background: {p.input_bg}; color: {p.text}; border: 1px solid {p.border};
    border-radius: 12px; padding: 0 12px; font-size: 13px;
    selection-background-color: {p.accent}; selection-color: {p.accent_text};
}}
QLineEdit#PlaylistLink:focus {{ border: 1px solid {p.accent}; }}
QPushButton#PasteBtn, QPushButton#OpenFolderBtn, QPushButton#HistoryBtn {{
    background: {p.surface}; color: {p.text}; border: 1px solid {p.border};
    border-radius: 12px; padding: 0 12px; font-size: 12px; font-weight: 600;
}}
QPushButton#PasteBtn:hover, QPushButton#OpenFolderBtn:hover, QPushButton#HistoryBtn:hover {{
    background: {p.surface_hover};
}}
QPushButton#OpenFolderBtn, QPushButton#HistoryBtn {{ border-radius: 10px; }}
QPushButton#DownloadBtn {{
    background: {p.accent}; color: {p.accent_text}; border: none; border-radius: 12px;
    font-size: 14px; font-weight: 800;
}}
QPushButton#DownloadBtn:hover {{ background: {p.accent_hover}; }}
QPushButton#DownloadBtn:pressed {{ background: {p.accent_pressed}; }}
QPushButton#DownloadBtn:disabled {{ background: {rgba(p.accent, 0.45)}; }}
QPushButton#DownloadBtn[stopping="true"] {{ background: {p.danger}; color: {p.danger_text}; }}
QLabel#statusMsg {{ color: {p.muted}; font-size: 12px; }}
QFrame#nowPanel {{ background: {p.surface}; border-radius: 14px; }}
QLabel#AlbumName {{ color: {p.muted}; font-size: 11px; font-weight: 600; }}
QLabel#MainSongName {{ font-size: 13px; font-weight: 700; }}
QLabel#CounterLabel {{ color: {p.muted}; font-size: 11px; }}
QProgressBar {{ background: {p.border}; border: none; border-radius: 3px; }}
QProgressBar::chunk {{ background: {p.accent}; border-radius: 3px; }}
QCheckBox {{ color: {p.text}; spacing: 7px; font-size: 12px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px; border-radius: 5px;
    border: 1px solid {rgba(p.muted, 0.7)}; background: {p.input_bg};
}}
QCheckBox::indicator:hover {{ border: 1px solid {p.accent}; }}
QCheckBox::indicator:checked {{
    background: {p.accent}; border: 1px solid {p.accent}; image: url({asset("check.svg")});
}}
QPushButton#Select_Home {{
    background: transparent; color: {p.muted}; border: none; font-size: 11px; padding: 2px 6px;
}}
QPushButton#Select_Home:hover {{ color: {p.accent_ink}; }}
QLabel#label_3 {{ color: {p.muted}; font-size: 11px; font-weight: 700; letter-spacing: 1px; }}
QLabel#CoverImg {{ background: {p.surface}; border-radius: 16px; color: {p.muted}; font-size: 44px; }}
QLabel#SongName {{ font-size: 16px; font-weight: 800; }}
QLabel#ArtistNameText {{ color: {p.muted}; font-size: 12px; }}
QLabel[caption="true"] {{ color: {p.muted}; font-size: 11px; }}
QLabel#AlbumText, QLabel#YearText {{ font-size: 12px; }}
QToolTip {{
    background: {p.surface}; color: {p.text}; border: 1px solid {p.border};
    border-radius: 6px; padding: 5px 8px;
}}
"""
