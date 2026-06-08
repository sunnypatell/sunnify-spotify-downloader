"""Spotify dark theme — single source of styling for Sunnify."""

import os
import sys

from PyQt5.QtGui import QFontDatabase


def _asset_url(name: str) -> str:
    """Absolute, forward-slashed file URL for a bundled asset (PyInstaller-aware).

    Qt stylesheet url() needs forward slashes even on Windows, and the assets
    live under sys._MEIPASS in a frozen build.
    """
    if getattr(sys, "frozen", False):
        base = os.path.join(sys._MEIPASS, "assets")
    else:
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
    return os.path.join(base, name).replace("\\", "/")


_CHEVRON_DOWN = _asset_url("chevron-down.svg")
_CHEVRON_UP = _asset_url("chevron-up.svg")

COLORS = {
    "base": "#121212",
    "surface": "#181818",
    "hover": "#282828",
    "input_bg": "#2A2A2A",
    "input_border": "#3E3E3E",
    "focus": "#1DB954",
    "text_primary": "#FFFFFF",
    "text_secondary": "#B3B3B3",
    "text_tertiary": "#6E6E73",
    "accent": "#1DB954",
    "accent_hover": "#1ED760",
    "accent_pressed": "#169C46",
    "download_text": "#000000",
    "progress_track": "#3E3E3E",
}

STYLESHEET = f"""
QMainWindow {{
    background-color: {COLORS["base"]};
}}

QWidget {{
    color: {COLORS["text_primary"]};
}}

QFrame#frame, QFrame#SONGINFORMATION {{
    background-color: {COLORS["surface"]};
    border: 1px solid {COLORS["hover"]};
    border-radius: 12px;
}}

QLabel {{
    background: transparent;
    color: {COLORS["text_primary"]};
    border: none;
}}

QLabel#title {{
    font-size: 20px;
    font-weight: 700;
    color: {COLORS["text_primary"]};
}}

QLabel#version, QLabel#author {{
    font-size: 11px;
    color: {COLORS["text_tertiary"]};
}}

QLabel#label_3, QLabel#label_7, QLabel#label_10, QLabel#PlaylistMsg_2,
QLabel#label_6, QLabel#label_9, QLabel#label_11, QLabel#label_8 {{
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 1px;
    color: {COLORS["text_secondary"]};
    text-transform: uppercase;
}}

QLabel#AlbumName, QLabel#statusMsg, QLabel#CounterLabel,
QLabel#SongName, QLabel#YearText, QLabel#ArtistNameText, QLabel#AlbumText {{
    font-size: 13px;
    color: {COLORS["text_primary"]};
}}

QLabel#MainSongName {{
    font-size: 15px;
    font-weight: 600;
    color: {COLORS["text_primary"]};
}}

QLabel#CoverImg {{
    background-color: {COLORS["hover"]};
    border: 1px solid {COLORS["hover"]};
    border-radius: 8px;
}}

QLineEdit#PlaylistLink {{
    background-color: {COLORS["input_bg"]};
    border: 1px solid {COLORS["input_border"]};
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 13px;
    color: {COLORS["text_primary"]};
    selection-background-color: {COLORS["accent"]};
    selection-color: {COLORS["download_text"]};
}}

QLineEdit#PlaylistLink:focus {{
    border: 1px solid {COLORS["focus"]};
}}

QPushButton#DownloadBtn {{
    background-color: {COLORS["accent"]};
    color: {COLORS["download_text"]};
    border: none;
    border-radius: 20px;
    font-size: 13px;
    font-weight: 700;
    padding: 8px 20px;
    min-height: 36px;
    min-width: 90px;
}}

QPushButton#DownloadBtn:hover {{
    background-color: {COLORS["accent_hover"]};
}}

QPushButton#DownloadBtn:pressed {{
    background-color: {COLORS["accent_pressed"]};
}}

QPushButton#DownloadBtn:disabled {{
    background-color: {COLORS["input_border"]};
    color: {COLORS["text_tertiary"]};
}}

QPushButton#SettingsBtn {{
    background-color: transparent;
    color: {COLORS["text_secondary"]};
    border: none;
    border-radius: 8px;
    font-size: 16px;
    padding: 4px 8px;
    min-width: 32px;
    min-height: 32px;
}}

QPushButton#SettingsBtn:hover {{
    color: {COLORS["text_primary"]};
    background-color: {COLORS["hover"]};
}}

QPushButton#SettingsBtn:pressed {{
    color: {COLORS["text_primary"]};
    background-color: {COLORS["input_border"]};
}}

QPushButton#Select_Home {{
    background-color: transparent;
    color: {COLORS["text_secondary"]};
    border: none;
    font-size: 12px;
    text-align: left;
    padding: 4px 0;
}}

QPushButton#Select_Home:hover {{
    color: {COLORS["accent_hover"]};
}}

QPushButton#Select_Home:pressed {{
    color: {COLORS["accent"]};
}}

QCheckBox {{
    spacing: 8px;
    color: {COLORS["text_primary"]};
    font-size: 13px;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 4px;
}}

QCheckBox::indicator:unchecked {{
    background-color: transparent;
    border: 2px solid {COLORS["text_tertiary"]};
}}

QCheckBox::indicator:unchecked:hover {{
    border-color: {COLORS["text_secondary"]};
}}

QCheckBox::indicator:checked {{
    background-color: {COLORS["accent"]};
    border: 2px solid {COLORS["accent"]};
    image: url(none);
}}

QProgressBar#SongDownloadprogress, QProgressBar#SongDownloadprogressBar {{
    background-color: {COLORS["progress_track"]};
    border: none;
    border-radius: 3px;
    min-height: 6px;
    max-height: 6px;
    text-align: center;
}}

QProgressBar#SongDownloadprogress::chunk, QProgressBar#SongDownloadprogressBar::chunk {{
    background-color: {COLORS["accent"]};
    border-radius: 3px;
}}

QComboBox {{
    background-color: {COLORS["input_bg"]};
    border: 1px solid {COLORS["input_border"]};
    border-radius: 8px;
    padding: 6px 12px;
    font-size: 13px;
    color: {COLORS["text_primary"]};
    min-height: 28px;
}}

QComboBox:focus, QComboBox:on {{
    border: 1px solid {COLORS["focus"]};
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 28px;
    border: none;
    border-top-right-radius: 8px;
    border-bottom-right-radius: 8px;
}}

QComboBox::down-arrow {{
    image: url({_CHEVRON_DOWN});
    width: 12px;
    height: 8px;
    margin-right: 10px;
}}

QComboBox QAbstractItemView {{
    background-color: {COLORS["surface"]};
    border: 1px solid {COLORS["input_border"]};
    border-radius: 8px;
    color: {COLORS["text_primary"]};
    selection-background-color: {COLORS["hover"]};
    selection-color: {COLORS["text_primary"]};
    padding: 4px;
    outline: none;
}}

QSpinBox {{
    background-color: {COLORS["input_bg"]};
    border: 1px solid {COLORS["input_border"]};
    border-radius: 8px;
    padding: 6px 8px;
    font-size: 13px;
    color: {COLORS["text_primary"]};
    min-height: 28px;
}}

QSpinBox:focus {{
    border: 1px solid {COLORS["focus"]};
}}

QSpinBox::up-button, QSpinBox::down-button {{
    subcontrol-origin: border;
    width: 20px;
    background-color: {COLORS["hover"]};
    border: none;
}}

QSpinBox::up-button {{
    subcontrol-position: top right;
    border-top-right-radius: 8px;
}}

QSpinBox::down-button {{
    subcontrol-position: bottom right;
    border-bottom-right-radius: 8px;
}}

QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
    background-color: {COLORS["input_border"]};
}}

QSpinBox::up-arrow {{
    image: url({_CHEVRON_UP});
    width: 10px;
    height: 7px;
}}

QSpinBox::down-arrow {{
    image: url({_CHEVRON_DOWN});
    width: 10px;
    height: 7px;
}}

QDialog {{
    background-color: {COLORS["base"]};
    color: {COLORS["text_primary"]};
}}

QLabel#settingsHeader {{
    font-size: 18px;
    font-weight: 700;
    color: {COLORS["text_primary"]};
    padding-bottom: 4px;
}}

QDialog QPushButton {{
    background-color: transparent;
    color: {COLORS["text_secondary"]};
    border: none;
    border-radius: 8px;
    font-size: 13px;
    padding: 8px 16px;
    min-height: 32px;
}}

QDialog QPushButton:hover {{
    color: {COLORS["text_primary"]};
    background-color: {COLORS["hover"]};
}}

QPushButton#settingsOkBtn {{
    background-color: {COLORS["accent"]};
    color: {COLORS["download_text"]};
    font-weight: 700;
    padding: 8px 24px;
}}

QPushButton#settingsOkBtn:hover {{
    background-color: {COLORS["accent_hover"]};
    color: {COLORS["download_text"]};
}}

QPushButton#settingsOkBtn:pressed {{
    background-color: {COLORS["accent_pressed"]};
    color: {COLORS["download_text"]};
}}

QPushButton#settingsCancelBtn {{
    background-color: transparent;
    color: {COLORS["text_secondary"]};
}}

QPushButton#settingsCancelBtn:hover {{
    color: {COLORS["text_primary"]};
    background-color: {COLORS["hover"]};
}}

QDialogButtonBox {{
    dialogbuttonbox-buttons-have-icons: 0;
}}

QToolTip {{
    background-color: {COLORS["surface"]};
    color: {COLORS["text_primary"]};
    border: 1px solid {COLORS["input_border"]};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}}
"""


def apply(app):
    """Apply the global Spotify-dark stylesheet and default font.

    Leads the family list with the platform's native UI font — San Francisco
    on macOS (i.e. the SF Pro look the design targets), Segoe UI on Windows —
    which always resolves, so Qt never hits the "missing font family" warning
    or the font-alias population cost on startup. The named faces remain as
    fallbacks for platforms whose system font isn't already one of them.
    """
    app.setStyleSheet(STYLESHEET)
    font = QFontDatabase.systemFont(QFontDatabase.GeneralFont)
    font.setPointSize(10)
    app.setFont(font)
