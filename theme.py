"""Sunnify design system.

One place for color, type, spacing, motion, and QSS composition so the UI
stays consistent and a designer (or future maintainer) can retheme the app
without hunting through widget code.

The palette keeps the purple identity of the original app (the icon is
purpleish and users love that vibe) but tightens it toward a dark, modern
SaaS look with the Spotify green kept only as the primary-action accent.
"""

from __future__ import annotations

from dataclasses import dataclass


#
# Color tokens. Every color in the app should come from here. The names are
# semantic (bg, surface, primary) rather than literal (purple, green) so the
# palette can be swapped without hunting for hex codes in widget code.
#
class Color:
    """Semantic color tokens for the Sunnify dark purple theme."""

    # Surface layers (backgrounds, outermost to innermost)
    bg_window = "#0d0a1a"  # window root (translucent backdrop behind card)
    bg_card = "#1a1230"  # primary card background
    bg_elevated = "#241a3f"  # raised surface (hover, focused input)
    bg_input = "#0f0a1f"  # input field background

    # Gradient stops for the card (preserves the "purpleish glow" feel)
    gradient_top = "#2a1a5e"  # top-left accent (brighter violet)
    gradient_mid = "#1e1140"  # midpoint (deep purple)
    gradient_bot = "#12081f"  # bottom-right (near-black violet)

    # Foreground (text + icons)
    fg_primary = "#f4f2fb"  # body text
    fg_secondary = "#b5adce"  # secondary labels
    fg_muted = "#7e7697"  # placeholder, disabled labels
    fg_on_primary = "#ffffff"  # text on the green CTA

    # Brand accents
    primary = "#8b5cf6"  # violet-500: brand interactive
    primary_hover = "#a78bfa"  # violet-400
    primary_pressed = "#7c3aed"  # violet-600

    # Primary CTA (download action). Spotify green pops against the purple.
    cta = "#1db954"
    cta_hover = "#1ed760"
    cta_pressed = "#169c46"

    # State colors
    success = "#22c55e"
    warning = "#f59e0b"
    error = "#ef4444"

    # Borders and dividers
    border = "#2e2451"
    border_focus = "#a78bfa"

    # Translucent overlays
    overlay = "rgba(13, 10, 26, 180)"


#
# Typography. Two-axis scale: role (display / heading / body / caption) x
# weight. Sizes picked so the app feels like a purpose-built desktop tool,
# not a cramped form.
#
class Font:
    """Font family + typographic scale."""

    # Cross-platform safe fallback chain. The first match wins on each OS.
    family = "SF Pro Display, Helvetica Neue, Inter, Segoe UI, Arial, system-ui, sans-serif"

    # Monospaced (for URLs in error reports, version strings, etc.)
    mono_family = "SF Mono, JetBrains Mono, Menlo, Consolas, Courier New, monospace"

    # Scale (in px). Resist the urge to add sizes outside this set.
    display = 22  # window title only
    heading = 16  # card section titles
    body = 13  # primary body text + inputs
    small = 11  # helper text, secondary info
    caption = 10  # footer, copyright, version


#
# Spacing. 4px base unit. Name by size, not purpose, so reading code stays
# easy (sp.md means "medium spacing", not "the spacing around the X widget").
#
@dataclass(frozen=True)
class Spacing:
    xs: int = 4
    sm: int = 8
    md: int = 12
    lg: int = 16
    xl: int = 24
    xxl: int = 32


sp = Spacing()


#
# Motion. Consistent durations so transitions feel like one language.
#
class Motion:
    fast = 150  # hover, focus
    base = 250  # default transition
    slow = 400  # panel open/close
    splash = 1600  # splash screen dwell


#
# QSS composition. A single string the MainWindow applies. This replaces the
# old Template.py setStyleSheet blob and keeps every color reference semantic.
#
def build_stylesheet() -> str:
    """Return the full application-wide Qt stylesheet.

    Composed from the tokens above. The gradient on the main card is the
    purple glow that gives Sunnify its identity; the rest of the palette is
    a dark theme with clear interactive states.
    """
    c = Color
    s = sp
    return f"""
    /* ============ Window root ============ */
    QWidget#centralwidget {{
        background: transparent;
    }}

    /* ============ Main card ============ */
    QFrame#frame {{
        background-color: qlineargradient(
            spread:pad, x1:0, y1:0, x2:1, y2:1,
            stop:0 {c.gradient_top},
            stop:0.55 {c.gradient_mid},
            stop:1 {c.gradient_bot}
        );
        border-radius: 16px;
        border: 1px solid {c.border};
    }}

    QFrame#SONGINFORMATION {{
        background-color: {c.bg_elevated};
        border-radius: 12px;
        border: 1px solid {c.border};
    }}

    /* ============ Typography ============ */
    QLabel {{
        color: {c.fg_primary};
        background: transparent;
    }}
    QLabel#title {{
        color: {c.fg_primary};
        font-size: {Font.display}px;
        font-weight: 700;
        letter-spacing: 0.5px;
    }}
    QLabel#author {{
        color: {c.fg_muted};
        font-size: {Font.small}px;
    }}
    QLabel#statusMsg, QLabel#statusIcon {{
        color: {c.fg_secondary};
        font-size: {Font.small}px;
    }}
    QLabel#statusLabel {{
        color: {c.fg_muted};
        font-size: {Font.small}px;
        font-weight: 600;
    }}
    QLabel#AlbumName {{
        color: {c.fg_secondary};
        font-size: {Font.body}px;
        font-weight: 600;
    }}
    QLabel#MainSongName {{
        color: {c.fg_primary};
        font-size: {Font.heading}px;
        font-weight: 600;
    }}
    QLabel#CounterLabel {{
        color: {c.fg_secondary};
        font-size: {Font.small}px;
    }}
    QLabel#version {{
        color: {c.fg_muted};
        font-size: {Font.caption}px;
    }}
    QLabel#sectionHeader {{
        color: {c.fg_muted};
        font-size: {Font.caption}px;
        font-weight: 700;
        letter-spacing: 1.2px;
    }}

    /* Preview panel labels */
    QLabel#SongName, QLabel#ArtistNameText,
    QLabel#AlbumText, QLabel#YearText {{
        color: {c.fg_primary};
        font-size: {Font.small}px;
    }}

    /* ============ Input field ============ */
    QLineEdit#PlaylistLink {{
        background-color: {c.bg_input};
        border: 1.5px solid {c.border};
        border-radius: 10px;
        color: {c.fg_primary};
        font-size: {Font.body}px;
        padding: {s.md}px {s.lg}px;
        selection-background-color: {c.primary};
    }}
    QLineEdit#PlaylistLink:focus {{
        border-color: {c.border_focus};
        background-color: {c.bg_elevated};
    }}
    QLineEdit#PlaylistLink:hover:!focus {{
        border-color: {c.primary};
    }}

    /* ============ Buttons ============ */
    /* Primary download CTA (Spotify green for recognition) */
    QPushButton#DownloadBtn {{
        background-color: {c.cta};
        color: {c.fg_on_primary};
        border: none;
        border-radius: 10px;
        font-size: {Font.body}px;
        font-weight: 700;
        letter-spacing: 0.3px;
        padding: {s.sm}px {s.md}px;
    }}
    QPushButton#DownloadBtn:hover {{ background-color: {c.cta_hover}; }}
    QPushButton#DownloadBtn:pressed {{ background-color: {c.cta_pressed}; }}
    QPushButton#DownloadBtn:disabled {{
        background-color: {c.border};
        color: {c.fg_muted};
    }}

    /* Ghost/secondary chrome buttons (close, settings, linkedin) */
    QPushButton#Closed, QPushButton#SettingsBtn, QPushButton#Select_Home {{
        background-color: transparent;
        color: {c.fg_secondary};
        border: none;
        border-radius: 6px;
        font-size: {Font.body}px;
        font-weight: 600;
    }}
    QPushButton#Closed:hover,
    QPushButton#SettingsBtn:hover,
    QPushButton#Select_Home:hover {{
        background-color: {c.bg_elevated};
        color: {c.fg_primary};
    }}
    QPushButton#Closed:pressed,
    QPushButton#SettingsBtn:pressed,
    QPushButton#Select_Home:pressed {{
        background-color: {c.border};
    }}

    /* ============ Checkboxes ============ */
    QCheckBox {{
        color: {c.fg_secondary};
        font-size: {Font.small}px;
        spacing: {s.sm}px;
    }}
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border-radius: 4px;
        border: 1.5px solid {c.border};
        background-color: {c.bg_input};
    }}
    QCheckBox::indicator:hover {{ border-color: {c.primary}; }}
    QCheckBox::indicator:checked {{
        background-color: {c.primary};
        border-color: {c.primary};
    }}

    /* ============ Progress bars ============ */
    QProgressBar {{
        background-color: {c.bg_input};
        border: none;
        border-radius: 4px;
        height: 6px;
        text-align: center;
        color: transparent;  /* hide percentage text */
    }}
    QProgressBar::chunk {{
        background-color: qlineargradient(
            spread:pad, x1:0, y1:0, x2:1, y2:0,
            stop:0 {c.primary}, stop:1 {c.cta}
        );
        border-radius: 4px;
    }}

    /* ============ Cover art placeholder ============ */
    QLabel#CoverImg {{
        background-color: {c.bg_input};
        border-radius: 8px;
        border: 1px solid {c.border};
    }}

    /* ============ Dialogs ============ */
    QDialog {{
        background-color: {c.bg_card};
        color: {c.fg_primary};
    }}
    QDialog QLabel {{ color: {c.fg_primary}; }}
    QDialog QPushButton {{
        background-color: {c.primary};
        color: {c.fg_on_primary};
        border: none;
        border-radius: 8px;
        padding: {s.sm}px {s.lg}px;
        font-weight: 600;
    }}
    QDialog QPushButton:hover {{ background-color: {c.primary_hover}; }}
    QDialog QPushButton:pressed {{ background-color: {c.primary_pressed}; }}

    /* ============ Combo box ============ */
    QComboBox {{
        background-color: {c.bg_input};
        border: 1.5px solid {c.border};
        border-radius: 8px;
        color: {c.fg_primary};
        font-size: {Font.body}px;
        padding: {s.sm}px {s.md}px;
        min-height: 24px;
    }}
    QComboBox:hover {{ border-color: {c.primary}; }}
    QComboBox::drop-down {{ border: none; width: 20px; }}
    QComboBox QAbstractItemView {{
        background-color: {c.bg_elevated};
        border: 1px solid {c.border};
        color: {c.fg_primary};
        selection-background-color: {c.primary};
        outline: none;
    }}

    /* ============ List widget (track progress) ============ */
    QListWidget {{
        background-color: {c.bg_input};
        border: 1px solid {c.border};
        border-radius: 8px;
        color: {c.fg_primary};
        outline: none;
    }}
    QListWidget::item {{ padding: {s.sm}px; }}
    QListWidget::item:selected {{
        background-color: {c.bg_elevated};
    }}

    /* ============ Scroll bars ============ */
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {c.border};
        border-radius: 4px;
        min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {c.primary}; }}
    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {{ height: 0; }}
    """
