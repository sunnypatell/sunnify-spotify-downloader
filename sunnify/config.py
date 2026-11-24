"""User settings: the registry every surface (GUI, CLI, engine) derives from."""

from __future__ import annotations

import contextlib
import json
import os
import sys
import tempfile

from sunnify.logs import log

# Supported output formats. "lossy" means quality/bitrate applies; "lossless"
# means the ffmpeg postprocessor ignores preferredquality.
SUPPORTED_FORMATS = {
    "mp3": {"ext": "mp3", "lossy": True},
    "m4a": {"ext": "m4a", "lossy": True},
    "opus": {"ext": "opus", "lossy": True},
    "flac": {"ext": "flac", "lossy": False},
    "wav": {"ext": "wav", "lossy": False},
}
SUPPORTED_QUALITIES = ("128", "192", "256", "320")
# "auto" keeps whatever rate the source stream has (YouTube audio is 48 kHz).
SUPPORTED_SAMPLE_RATES = ("auto", "44100", "48000")
# whole-window scale in percent, on top of the system's own display scaling
SUPPORTED_UI_SCALES = ("75", "90", "100", "125", "150", "175", "200")
# "auto" follows the system locale: Malay gets Bahasa Melayu, everything else English
SUPPORTED_LANGUAGES = ("auto", "en", "ms")
# "system" follows the OS light/dark setting (Qt 6.5+ reports it)
SUPPORTED_THEMES = ("system", "dark", "light")


class _Setting:
    """One user setting: config key, validation, scraper wiring, CLI surface."""

    __slots__ = ("choices", "cli_flag", "default", "help", "key", "kind", "scraper_kwarg")

    def __init__(self, key, default, kind, choices=(), scraper_kwarg=None, cli_flag=None, help=""):
        self.key = key
        self.default = default
        self.kind = kind  # "choice" | "bool" | "path"
        self.choices = choices
        self.scraper_kwarg = scraper_kwarg
        self.cli_flag = cli_flag
        self.help = help

    def coerce(self, value):
        """Validated value or the default - never raises on user data."""
        if self.kind == "bool":
            return value if isinstance(value, bool) else self.default
        if self.kind == "choice":
            return value if value in self.choices else self.default
        return value if isinstance(value, str) or value is None else self.default


# Single source of truth for user settings. Config load/validation, scraper
# construction, and every CLI flag derive from this - a new setting added
# here reaches the CLI with zero CLI changes (the dialog row stays bespoke).
SETTINGS = (
    _Setting("download_path", None, "path", help="where downloads land"),
    _Setting(
        "format",
        "mp3",
        "choice",
        tuple(SUPPORTED_FORMATS),
        scraper_kwarg="audio_format",
        cli_flag="--format",
        help="audio format",
    ),
    _Setting(
        "quality",
        "192",
        "choice",
        SUPPORTED_QUALITIES,
        scraper_kwarg="audio_quality",
        cli_flag="--quality",
        help="bitrate in kbps, lossy formats only",
    ),
    _Setting(
        "sample_rate",
        "auto",
        "choice",
        SUPPORTED_SAMPLE_RATES,
        scraper_kwarg="sample_rate",
        cli_flag="--sample-rate",
        help="output sample rate, applies to mp3/flac/wav",
    ),
    _Setting(
        "include_track_number",
        False,
        "bool",
        scraper_kwarg="include_track_number",
        cli_flag="--track-numbers",
        help="prefix filenames with playlist position",
    ),
    _Setting(
        "artist_first",
        False,
        "bool",
        scraper_kwarg="artist_first",
        cli_flag="--artist-first",
        help='name files "Artist - Song" instead of "Song - Artist"',
    ),
    _Setting(
        "title_only",
        False,
        "bool",
        scraper_kwarg="title_only",
        cli_flag="--title-only",
        help="name files by song title alone; the artist stays in the tags",
    ),
    _Setting(
        "loose_match",
        False,
        "bool",
        scraper_kwarg="loose_match",
        cli_flag="--loose-match",
        help="fall back to the closest result when strict matching finds nothing",
    ),
    _Setting(
        "lyrics",
        False,
        "bool",
        scraper_kwarg="lyrics",
        cli_flag="--lyrics",
        help="embed lyrics from LRCLIB, plus a .lrc file when they are time-synced",
    ),
    _Setting(
        "cookies_file",
        None,
        "path",
        scraper_kwarg="cookies_file",
        cli_flag="--cookies",
        help="youtube cookies.txt for networks youtube gates (needs deno or node 22+)",
    ),
    _Setting(
        "ui_scale",
        "100",
        "choice",
        SUPPORTED_UI_SCALES,
        help="window and text size in percent, on top of the system's display scaling",
    ),
    _Setting(
        "language",
        "auto",
        "choice",
        SUPPORTED_LANGUAGES,
        help="desktop app language: auto (follow the system), en, or ms (Bahasa Melayu)",
    ),
    _Setting(
        "theme",
        "system",
        "choice",
        SUPPORTED_THEMES,
        help="desktop app colours: system, dark, or light",
    ),
    _Setting(
        "notify",
        True,
        "bool",
        help="tell the desktop when a download finishes while Sunnify is in the background",
    ),
)


def scraper_kwargs_from(settings: dict) -> dict:
    """Registry-derived MusicScraper kwargs from a config/settings dict."""
    return {s.scraper_kwarg: settings.get(s.key, s.default) for s in SETTINGS if s.scraper_kwarg}


def _config_dir() -> str:
    """Return the per-user config directory, creating it if needed."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    elif sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME", os.path.join(os.path.expanduser("~"), ".config"))
    path = os.path.join(base, "Sunnify")
    os.makedirs(path, exist_ok=True)
    return path


def _config_path() -> str:
    return os.path.join(_config_dir(), "config.json")


# desktop-app state saved next to the settings: remembered, never a CLI flag or
# a row in Settings, and hidden from `sunnify config`
UI_STATE_DEFAULTS = {
    "star_prompt_shown": False,  # the one-time star ask has been shown
    "show_preview": False,  # the song panel was left open
    "write_tags": True,  # "Add tags" on the main window
}


def load_config() -> dict:
    """Load persisted user config. Missing or corrupt file returns defaults.

    Every user setting is validated through the SETTINGS registry; the
    UI_STATE_DEFAULTS keys are internal state, not settings, and must be bools."""
    defaults = {s.key: s.default for s in SETTINGS}
    defaults["version"] = 1
    defaults.update(UI_STATE_DEFAULTS)
    try:
        with open(_config_path(), encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return defaults
        for s in SETTINGS:
            if s.key in data:
                defaults[s.key] = s.coerce(data[s.key])
        for key in UI_STATE_DEFAULTS:
            if isinstance(data.get(key), bool):
                defaults[key] = data[key]
        return defaults
    except (OSError, json.JSONDecodeError):
        return defaults


def write_json_atomic(path: str, data) -> None:
    """Write JSON so a crash mid-write leaves the old file, never half of a new one."""
    folder = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(prefix=".sunnify-", suffix=".json", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.remove(tmp)
        raise


def save_config(config: dict) -> None:
    """Persist user config to disk. Best-effort, swallows IO errors."""
    try:
        write_json_atomic(_config_path(), config)
    except OSError as exc:
        log.warning("could not save config: %s", exc)
