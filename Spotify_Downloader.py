#
"""
Sunnify (Spotify Downloader)
Copyright (C) 2024 Sunny Patel <sunnypatel124555@gmail.com>

EDUCATIONAL PROJECT DISCLAIMER:
This software is a student portfolio project developed for educational purposes only.
It is intended to demonstrate software engineering skills and is provided free of charge.
Users are solely responsible for ensuring compliance with applicable laws in their jurisdiction.
This software should only be used with content you own or have permission to download.
See DISCLAIMER.md for full terms.

For the program to work, the playlist URL pattern must follow the format of
/playlist/abcdefghijklmnopqrstuvwxyz... If the program stops working, email
<sunnypatel124555@gmail.com> or open an issue in the repository.
"""

from __future__ import annotations

__version__ = "2.1.0"

import atexit
import concurrent.futures
import contextlib
import faulthandler
import logging
import os
import platform
import re
import signal
import sys
import threading
import webbrowser
from logging.handlers import RotatingFileHandler

import requests
from mutagen.easyid3 import EasyID3
from mutagen.id3 import APIC, ID3
from PyQt6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QSize,
    Qt,
    QThread,
    pyqtSignal,
    pyqtSlot,
)
from PyQt6.QtGui import QCursor, QImage, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)
from yt_dlp import YoutubeDL

from spotifydown_api import (
    ExtractionError,
    NetworkError,
    PlaylistClient,
    PlaylistInfo,
    RateLimitError,
    SpotifyDownAPIError,
    cap_filename,
    detect_spotify_url_type,
    extract_playlist_id,
    sanitize_filename,
)
from Template import Ui_MainWindow

# Module logger. Stays a no-op (no handlers) until _setup_logging() runs at
# startup, so importing this module in tests stays silent and writes nothing.
log = logging.getLogger("sunnify")


def _log_excepthook(exc_type, exc, tb):
    """Route uncaught main-thread exceptions to the log before the default handler."""
    # a clean ctrl+c is not a crash worth a critical-level dump
    if not issubclass(exc_type, KeyboardInterrupt):
        with contextlib.suppress(Exception):
            log.critical("uncaught exception", exc_info=(exc_type, exc, tb))
    if sys.stderr is not None:  # windowed builds have no stderr to write to
        sys.__excepthook__(exc_type, exc, tb)


def _thread_excepthook(args):
    """Same, for python threads; qt threads log inside their own run()."""
    if issubclass(args.exc_type, SystemExit):
        return
    with contextlib.suppress(Exception):
        log.critical(
            "uncaught exception in thread %s",
            args.thread.name if args.thread else "?",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )


def _install_crash_handlers() -> None:
    """Make every abnormal exit land in the log; logging is our only diagnostic."""
    sys.excepthook = _log_excepthook
    threading.excepthook = _thread_excepthook
    # faulthandler catches native crashes (qt/ffmpeg segfaults) excepthook can't;
    # crash.log sits next to sunnify.log and stays open for the process lifetime.
    with contextlib.suppress(Exception):
        crash_path = os.path.join(os.path.dirname(log_file_path()), "crash.log")
        faulthandler.enable(open(crash_path, "a"))  # noqa: SIM115
    atexit.register(lambda: log.info("==== sunnify session end ===="))


class _YtdlpLog:
    """Bridge yt-dlp's own output into our log and remember the last error.

    With ignoreerrors=True a failed download won't raise, so capturing error()
    here is the only way to record *why* no audio file landed (bot-block vs
    unavailable vs format vs nsig). Routine yt-dlp chatter goes to our DEBUG so
    the default INFO log stays lean.
    """

    def __init__(self):
        self.last_error = None

    def debug(self, msg):
        log.debug("yt-dlp: %s", msg)

    info = debug

    def warning(self, msg):
        log.debug("yt-dlp warning: %s", msg)

    def error(self, msg):
        self.last_error = msg
        log.debug("yt-dlp error: %s", msg)


def get_ffmpeg_path():
    """Get path to FFmpeg - checks bundled first, then system paths."""
    # Check bundled FFmpeg first (for PyInstaller builds)
    if getattr(sys, "frozen", False):
        base_path = sys._MEIPASS
        if sys.platform == "win32":
            ffmpeg = os.path.join(base_path, "ffmpeg", "ffmpeg.exe")
        else:
            ffmpeg = os.path.join(base_path, "ffmpeg", "ffmpeg")
        if os.path.exists(ffmpeg):
            return os.path.join(base_path, "ffmpeg")

    # Check common system paths (for homebrew/system installs)
    ffmpeg_name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    common_paths = [
        "/opt/homebrew/bin",  # macOS ARM homebrew
        "/usr/local/bin",  # macOS Intel homebrew / Linux
        "/usr/bin",  # Linux system
    ]

    for path in common_paths:
        ffmpeg = os.path.join(path, ffmpeg_name)
        if os.path.exists(ffmpeg):
            return path

    # Check if ffmpeg is in PATH
    import shutil

    ffmpeg_in_path = shutil.which("ffmpeg")
    if ffmpeg_in_path:
        return os.path.dirname(ffmpeg_in_path)

    return None


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

# Resume manifest: a JSON-lines file dropped inside each playlist/album folder
# recording which tracks already downloaded. On a re-run we skip those tracks
# before fetching their metadata, so a huge playlist throttled by Spotify's
# rate limit can be finished across several sessions instead of one long sit
# (closes #40).
MANIFEST_FILENAME = ".sunnify-manifest.jsonl"


def _config_dir() -> str:
    """Return the per-user config directory, creating it if needed."""
    import json as _json  # noqa: F401 (used by load/save)

    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    elif sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME", os.path.join(os.path.expanduser("~"), ".config"))
    path = os.path.join(base, "Sunnify")
    os.makedirs(path, exist_ok=True)
    return path


def _log_dir() -> str:
    """Return the per-user log directory path (does not create it).

    Pure path computation, no filesystem side effects, so callers that only
    need the string (e.g. a settings tooltip) don't create stray folders;
    setup_logging() and _open_logs() create the dir when they actually use it.

    Uses each platform's conventional spot for app logs (not config), so the
    files are where a user (or a support request) would expect them:
      windows -> %LOCALAPPDATA%\\Sunnify\\logs
      macOS   -> ~/Library/Logs/Sunnify
      linux   -> $XDG_STATE_HOME/sunnify/logs (defaults to ~/.local/state)
    """
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA", os.path.expanduser("~"))
        path = os.path.join(base, "Sunnify", "logs")
    elif sys.platform == "darwin":
        path = os.path.join(os.path.expanduser("~"), "Library", "Logs", "Sunnify")
    else:
        base = os.environ.get(
            "XDG_STATE_HOME", os.path.join(os.path.expanduser("~"), ".local", "state")
        )
        path = os.path.join(base, "sunnify", "logs")
    return path


def log_file_path() -> str:
    """Absolute path of the current log file (used by the 'open logs' action)."""
    return os.path.join(_log_dir(), "sunnify.log")


def setup_logging() -> str:
    """Configure file logging once; return the log file path.

    Rotating handler caps disk use at ~6MB total (1MB x 5 backups) so logs are
    diagnostic, never bloat. Idempotent: safe to call more than once. The line
    format is deliberately dense (timestamp, level, function:line) so a single
    log pasted into an issue is enough to pinpoint where a download went wrong.
    A session header records the environment every launch.
    """
    if any(getattr(h, "_sunnify", False) for h in log.handlers):
        return log_file_path()

    path = log_file_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    handler = RotatingFileHandler(
        path, maxBytes=1_000_000, backupCount=5, encoding="utf-8", delay=True
    )
    handler._sunnify = True  # tag so we don't double-attach on re-call
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)-7s [%(funcName)s:%(lineno)d] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    # default INFO stays lean (scales with failures, not track count); set
    # SUNNIFY_DEBUG=1 to get the full per-track + yt-dlp trail for hard cases.
    level = logging.DEBUG if os.environ.get("SUNNIFY_DEBUG") else logging.INFO
    log.setLevel(level)
    log.addHandler(handler)
    log.propagate = False

    try:
        ytdlp_ver = __import__("yt_dlp").version.__version__
    except Exception:
        ytdlp_ver = "?"
    log.info("==== sunnify session start ====")
    log.info(
        "version=%s platform=%s python=%s yt-dlp=%s",
        __version__,
        f"{sys.platform}-{platform.machine()}",
        platform.python_version(),
        ytdlp_ver,
    )
    log.info("ffmpeg=%s", get_ffmpeg_path() or "(not found)")
    log.info("logs=%s level=%s", path, logging.getLevelName(level))
    _install_crash_handlers()
    return path


def _config_path() -> str:
    return os.path.join(_config_dir(), "config.json")


def load_config() -> dict:
    """Load persisted user config. Missing or corrupt file returns defaults."""
    import json

    defaults = {
        "version": 1,
        "download_path": None,
        "format": "mp3",
        "quality": "192",
        "include_track_number": False,
        "loose_match": False,
        "star_prompt_shown": False,
    }
    try:
        with open(_config_path(), encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return defaults
        defaults.update({k: v for k, v in data.items() if k in defaults})
        if defaults["format"] not in SUPPORTED_FORMATS:
            defaults["format"] = "mp3"
        if defaults["quality"] not in SUPPORTED_QUALITIES:
            defaults["quality"] = "192"
        if not isinstance(defaults["include_track_number"], bool):
            defaults["include_track_number"] = False
        if not isinstance(defaults["loose_match"], bool):
            defaults["loose_match"] = False
        if not isinstance(defaults["star_prompt_shown"], bool):
            defaults["star_prompt_shown"] = False
        return defaults
    except (OSError, json.JSONDecodeError):
        return defaults


def save_config(config: dict) -> None:
    """Persist user config to disk. Best-effort, swallows IO errors."""
    import json

    try:
        with open(_config_path(), "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
    except OSError as exc:
        log.warning("could not save config: %s", exc)


GITHUB_REPO = "sunnypatell/sunnify-spotify-downloader"
_LATEST_RELEASE_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
_RELEASES_PAGE = f"https://github.com/{GITHUB_REPO}/releases/latest"


def _parse_version(s: str) -> tuple:
    """'v2.0.13' / '2.0.13' / '2.0.13-beta' -> (2, 0, 13). Stops at the first non-int part."""
    parts = []
    for chunk in (s or "").strip().lstrip("vV").split("."):
        num = ""
        for ch in chunk:
            if ch.isdigit():
                num += ch
            else:
                break
        if not num:
            break
        parts.append(int(num))
    return tuple(parts)


def _is_newer_version(latest: str, current: str) -> bool:
    """True if latest is a strictly newer release than current (numeric, not lexical)."""
    lv, cv = _parse_version(latest), _parse_version(current)
    return bool(lv) and lv > cv


def _check_for_update(current: str, timeout: int = 5):
    """Return (latest_version, release_url) if a newer release exists, else None.

    Fail-silent (returns None) on any network/parse error so launch is never
    blocked or crashed by the check.
    """
    try:
        r = requests.get(
            _LATEST_RELEASE_API,
            timeout=timeout,
            headers={"Accept": "application/vnd.github+json"},
        )
        if r.status_code != 200:
            log.debug("update check: github api returned %s", r.status_code)
            return None
        data = r.json()
        tag = data.get("tag_name") or ""
        url = data.get("html_url") or _RELEASES_PAGE
        if _is_newer_version(tag, current):
            return (tag.lstrip("vV"), url)
        log.debug("update check: on latest (%s, newest %s)", current, tag or "?")
        return None
    except Exception as exc:  # network/parse must never disrupt launch
        log.debug("update check skipped: %s", exc)
        return None


class UpdateCheckThread(QThread):
    """Runs _check_for_update off the UI thread and signals if a release is newer."""

    update_available = pyqtSignal(str, str)  # (latest_version, release_url)

    def __init__(self, current_version: str):
        super().__init__()
        self._current = current_version

    def run(self):
        result = _check_for_update(self._current)
        if result:
            self.update_available.emit(result[0], result[1])


class MusicScraper(QThread):
    PlaylistCompleted = pyqtSignal(str)
    PlaylistID = pyqtSignal(str)
    song_Album = pyqtSignal(str)
    song_meta = pyqtSignal(dict)
    add_song_meta = pyqtSignal(dict)
    count_updated = pyqtSignal(int)
    dlprogress_signal = pyqtSignal(int)
    Resetprogress_signal = pyqtSignal(int)
    error_signal = pyqtSignal(str)  # Signal for error messages to UI

    # Max concurrent track downloads. 4 is the measured sweet spot:
    # linear speedup through 4, diminishing returns past 6 (CPU-bound ffmpeg).
    MAX_WORKERS = 4

    def __init__(
        self,
        cancel_event: threading.Event | None = None,
        *,
        audio_format: str = "mp3",
        audio_quality: str = "192",
        include_track_number: bool = False,
        loose_match: bool = False,
    ):
        super().__init__()
        self.counter = 0  # Initialize counter to zero
        self.session = requests.Session()
        self.spotifydown_api = None
        self._cancel_event = cancel_event or threading.Event()
        self._failed_tracks: list[str] = []  # Track failed downloads
        # Output options. audio_format must be a key of SUPPORTED_FORMATS;
        # audio_quality only applies to lossy formats (mp3/m4a/opus).
        self.audio_format = audio_format if audio_format in SUPPORTED_FORMATS else "mp3"
        self.audio_quality = audio_quality if audio_quality in SUPPORTED_QUALITIES else "192"
        self.include_track_number = bool(include_track_number)
        # opt-in: when strict title/artist matching fails, fall back to the
        # duration-closest youtube result (recovers cross-script matches);
        # off by default so the wrong-audio safeguard (#52) stays the default.
        self.loose_match = bool(loose_match)
        self._counter_lock = threading.Lock()
        self._failed_lock = threading.Lock()
        self._filename_lock = threading.Lock()
        self._manifest_lock = threading.Lock()
        self._manifest_path: str | None = None
        self._in_flight_files: set[str] = set()
        # Set to True during parallel playlist downloads so workers can suppress
        # per-track UI noise (label flicker, thumbnail spam, progress bar jitter)
        # that only makes sense for a single active download.
        self._parallel_mode = False
        self._total_tracks = 0

    def is_cancelled(self) -> bool:
        """Check if cancellation has been requested."""
        return self._cancel_event.is_set()

    def _get_user_friendly_error(self, error: Exception, track_title: str = "") -> str:
        """Convert exception to user-friendly error message."""
        if isinstance(error, RateLimitError):
            return "Rate limited by Spotify - waiting..."
        if isinstance(error, NetworkError):
            return "Network error - retrying..."
        if isinstance(error, ExtractionError):
            return f"Could not access '{track_title}' - may be unavailable"
        if "HTTP Error 429" in str(error):
            return "YouTube rate limit - waiting..."
        error_text = str(error).lower()
        if (
            "no video formats" in error_text
            or "no playable audio source" in error_text
            or "unavailable" in error_text
        ):
            return f"'{track_title}' not found on YouTube"
        return f"Error: {str(error)[:50]}"

    def ensure_spotifydown_api(self):
        if self.spotifydown_api is None:
            self.spotifydown_api = PlaylistClient(session=self.session)
        return self.spotifydown_api

    def sanitize_text(self, text):
        """Sanitize text for filename usage."""
        return sanitize_filename(text, allow_spaces=True)

    def format_playlist_name(self, metadata: PlaylistInfo):
        owner = metadata.owner or "Spotify"
        return f"{metadata.name} - {owner}".strip(" -")

    def prepare_playlist_folder(self, base_folder, playlist_name):
        os.makedirs(base_folder, exist_ok=True)
        # Folder names go through the same documented cross-platform sanitizer as
        # track files (sanitize_filename): drops only the Windows-reserved
        # punctuation + control chars, trims trailing dots/spaces, escapes
        # reserved device names (CON, NUL, ...) and NFC-normalizes, per the
        # Microsoft + POSIX filename rules. The old ascii-only allowlist missed
        # the reserved-device-name case (a playlist named "CON" produced an
        # uncreatable folder on Windows) and silently dropped punctuation.
        safe_name = sanitize_filename(playlist_name)
        if not safe_name or safe_name == "Unknown":
            safe_name = "Sunnify Playlist"
        playlist_folder = os.path.join(base_folder, safe_name)
        # Backward-compat: older builds dropped punctuation via an ascii-only
        # allowlist (e.g. "Name - Owner" -> "Name  Owner"). If that older folder
        # already exists, keep using it so a re-run resumes into the same folder
        # instead of orphaning the previous download + its manifest (#40).
        legacy_name = "".join(
            ch for ch in playlist_name if ch.isalnum() or ch in (" ", "_")
        ).strip()
        legacy_folder = os.path.join(base_folder, legacy_name)
        if legacy_name and legacy_name != safe_name and os.path.isdir(legacy_folder):
            playlist_folder = legacy_folder
        try:
            os.makedirs(playlist_folder, exist_ok=True)
        except OSError:
            log.error("could not create playlist folder %r", playlist_folder, exc_info=True)
            raise
        return playlist_folder

    @staticmethod
    def _widen_search(search_query: str) -> str:
        """Search several YouTube results instead of only the top hit.

        A track's #1 result can be region-locked or removed; `ytsearch1`
        fails the whole download in that case (closes #42). Widening to
        `ytsearch5` lets yt-dlp skip unavailable results and download the
        first one that actually plays.
        """
        if search_query.startswith("ytsearch1:"):
            return "ytsearch5:" + search_query[len("ytsearch1:") :]
        return search_query

    @staticmethod
    def _simplify_search(search_query: str) -> str:
        """Strip parenthetical/bracketed qualifiers for a looser fallback.

        Hyper-specific titles (classical works like `(Wiegenlied, Op. 49,
        No. 4)`, tone tracks like `(528 Hz)`) can return zero YouTube
        matches. Dropping the qualifiers widens the net on a second attempt.
        Returns the original query unchanged if there is nothing to strip.
        """
        _, sep, terms = search_query.partition(":")
        if not sep:
            terms = search_query
        stripped = re.sub(r"[\(\[\{].*?[\)\]\}]", " ", terms)
        stripped = re.sub(r"\s+", " ", stripped).strip()
        if not stripped or stripped == terms.strip():
            return search_query
        return f"ytsearch5:{stripped}"

    # Max gap (seconds) between the Spotify track length and a YouTube
    # candidate's length for the candidate to count as the "same" recording.
    # The top YouTube hit is often the music video (extra intro/skit/outro) or
    # an extended/remix cut, which plays as a different song even though the
    # filename is right. Matching on duration steers us to the real audio.
    _DURATION_TOLERANCE_S = 7

    # Wider tolerance for the title-and-duration combined check: if a candidate
    # has the right title but its duration is wildly off (>30s), it's almost
    # certainly a remix / live / extended edit of the right song rather than
    # the original. Better to fail loudly than ship something that fades out
    # in the wrong place.
    _DURATION_TOLERANCE_S_WIDE = 30

    @staticmethod
    def _normalize_title(s: str | None) -> str:
        """Lowercase, strip diacritics, drop bracketed segments + `feat./ft.`
        tails, collapse to alphanumerics + spaces. Used on BOTH sides of
        title comparison.

        Critically: this does NOT split on ` - ` because YouTube titles
        commonly use the `Artist - Song` convention; splitting would turn
        "The Weeknd - Blinding Lights" into just "The Weeknd" and lose the
        song name. Spotify-side variant stripping (`Title - Remastered`)
        is handled separately in `_spotify_title_core`.
        """
        if not s:
            return ""
        import unicodedata

        # NFKD + drop combining marks: "Café" -> "Cafe"
        s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
        s = s.lower()
        s = re.sub(r"\([^)]*\)", " ", s)  # "Hello (Remix)" -> "Hello "
        s = re.sub(r"\[[^\]]*\]", " ", s)  # "Hello [Edit]" -> "Hello "
        s = re.sub(r"\b(feat\.?|ft\.?)\s+.*$", "", s, flags=re.IGNORECASE)
        # Strip apostrophes BEFORE the general punctuation->space step so
        # "I'm" becomes "im" not "i m".
        s = s.replace("'", "").replace("’", "")
        s = re.sub(r"[^a-z0-9\s]", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    @staticmethod
    def _spotify_title_core(s: str | None) -> str:
        """Drop the ` - Variant` suffix Spotify adds to differentiate releases.

        Examples:
            "Bohemian Rhapsody - Remastered 2011" -> "Bohemian Rhapsody"
            "Hello - Live"                        -> "Hello"
            "Sweet Disposition - Remix Edit"      -> "Sweet Disposition"
            "Take-Off"                            -> "Take-Off" (literal hyphen, no spaces)
            "Mi Gente"                            -> "Mi Gente"

        Only applied to the Spotify-side title before fuzzy comparison so
        a YouTube upload titled just "Bohemian Rhapsody" still matches.
        Don't apply this to YouTube titles - they use ` - ` for
        `Artist - Song` and the strip would lose the song name.
        """
        if not s:
            return ""
        return s.split(" - ", 1)[0]

    @classmethod
    def _title_plausibly_matches(cls, yt_title: str | None, expected_title: str | None) -> bool:
        """True when the YouTube candidate's title could reasonably be the
        Spotify track. The Spotify side gets its variant suffix dropped
        first so "Hello - Live" matches a plain "Hello" upload; the YouTube
        side is normalized as-is (its ` - ` is usually `Artist - Song`).
        Substring match for titles >= 4 chars, word-boundary match for
        shorter ones (so a single-letter song name like "i" doesn't match
        every YouTube video)."""
        yt = cls._normalize_title(yt_title)
        target = cls._normalize_title(cls._spotify_title_core(expected_title))
        if not target or not yt:
            return False
        if len(target) >= 4:
            return target in yt
        return target in yt.split()

    def _select_youtube_match(
        self, search_query, expected_duration_s, expected_title=None, expected_artists=None
    ):
        """Return the best YouTube watch URL for a search, or None.

        Selection policy (closes #52):
          1. Filter to candidates whose title plausibly matches the Spotify
             track title (substring / word match on a normalized form).
             Rules out the failure mode where YouTube's top hit is a
             DIFFERENT track by the SAME artist with a similar duration -
             e.g. searching "Mi Gente DJ Goja audio" returns "Dj Goja -
             Mi Chico" at the top, only ~2s off the real Mi Gente, and the
             prior pure-duration matcher would happily pick it and write
             Mi Gente metadata onto Mi Chico audio.
          2. Prefer the subset that ALSO has an artist plausibly appearing
             in the YouTube title. Falls back to the title-only pool if no
             candidate matches both - artist isn't always in the YouTube
             title for legitimate uploads.
          3. Among the resulting pool, pick the duration-closest if duration
             is known, but reject the whole result if even the best
             candidate's duration is >30s off the Spotify track - that means
             the closest title-matching upload is a remix / live cover /
             extended edit, and shipping a 5-minute remix under a 2-minute
             track's metadata still corrupts the library.
          4. If no candidate's title passes, return None. The caller treats
             that as "not found on YouTube" - strictly better than shipping
             the wrong audio under the right cover.

        `expected_title` + `expected_artists` are optional so legacy callers
        that haven't been updated still work via the older trust-the-top-
        hit-unless-duration-is-clearly-off policy.
        """
        select_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": True,
            "ignoreerrors": True,
            "retries": 5,
            "socket_timeout": 15,
            "concurrent_fragment_downloads": 4,
        }
        log.debug(
            "yt search: query=%r title=%r artists=%r dur=%ss",
            search_query,
            expected_title,
            expected_artists,
            expected_duration_s,
        )
        try:
            with YoutubeDL(select_opts) as ydl:
                info = ydl.extract_info(search_query, download=False)
        except Exception as exc:
            # The single most useful log line for triage: a real exception here
            # (bot-challenge, SSL, network, region block) is otherwise invisible
            # because the caller only ever sees "not found on YouTube".
            log.warning("yt search raised %s: %s", type(exc).__name__, str(exc)[:300])
            return None
        entries = [e for e in (info or {}).get("entries", []) if e and e.get("id")]
        if not entries:
            # Empty results with no exception is the classic bot-block / rate-limit
            # / region signature. Distinct from "found results but filtered out".
            log.warning(
                "yt search returned 0 entries for %r (bot-block/network/region?)", search_query
            )
            return None
        log.debug("yt search returned %d entries", len(entries))

        if expected_title:
            title_ok = [
                e for e in entries if self._title_plausibly_matches(e.get("title"), expected_title)
            ]
            if not title_ok:
                log.info(
                    "title filter rejected all %d candidates for %r (e.g. %r)",
                    len(entries),
                    expected_title,
                    (entries[0].get("title") if entries else None),
                )
                if self.loose_match:
                    return self._loose_pick(entries, expected_duration_s)
                return None

            # When the artists are known, require at least one to appear in
            # the YouTube title alongside the song name. This rejects
            # "right-song-name, wrong-uploader's-remix" - e.g. Spotify's
            # Mi Gente by DJ Goja vs YouTube's SkywiinPROD's Mi Gente Remix.
            # User feedback (#52) was crystal clear: prefer not-found over
            # wrong audio. Falls back to title-only matching when no
            # expected_artists is given (legacy callers, single-track flows
            # before the v2.0.9 wire-up).
            pool = title_ok
            if expected_artists:
                # Split FIRST on collaboration separators (commas / ampersands
                # / `feat`), then normalize each artist independently. Doing
                # this in the other order loses commas during normalization
                # (they become spaces) and collapses the whole multi-artist
                # string into one token nobody would match.
                raw_tokens = re.split(
                    r"[,&]+|\s+(?:feat\.?|ft\.?)\s+",
                    expected_artists,
                    flags=re.IGNORECASE,
                )
                artist_tokens = [self._normalize_title(t) for t in raw_tokens]
                artist_tokens = [t for t in artist_tokens if t]
                if artist_tokens:
                    pool = [
                        e
                        for e in title_ok
                        if any(
                            artist in self._normalize_title(e.get("title") or "")
                            for artist in artist_tokens
                        )
                    ]
                    if not pool:
                        log.info(
                            "artist filter rejected all %d title-matches (artists=%r)",
                            len(title_ok),
                            expected_artists,
                        )
                        if self.loose_match:
                            return self._loose_pick(title_ok, expected_duration_s)
                        return None

            chosen = pool[0]
            if expected_duration_s:
                timed = [e for e in pool if e.get("duration")]
                if timed:
                    chosen = min(timed, key=lambda e: abs(e["duration"] - expected_duration_s))
                    # Even if title+artist both match, refuse a candidate
                    # whose duration is wildly off the Spotify track - that
                    # means it's a live cover / extended mix and shipping
                    # it under the original's metadata still corrupts the
                    # library.
                    off = abs(chosen["duration"] - expected_duration_s)
                    if off > self._DURATION_TOLERANCE_S_WIDE:
                        log.info(
                            "closest candidate duration off by %.0fs (>%ss), rejecting",
                            off,
                            self._DURATION_TOLERANCE_S_WIDE,
                        )
                        return None
            log.debug("selected youtube video %s", chosen["id"])
            return f"https://www.youtube.com/watch?v={chosen['id']}"

        # Legacy path - kept for any caller that hasn't been updated yet.
        chosen = entries[0]
        if expected_duration_s:
            top_duration = chosen.get("duration")
            top_off = top_duration is None or (
                abs(top_duration - expected_duration_s) > self._DURATION_TOLERANCE_S
            )
            if top_off:
                timed = [e for e in entries if e.get("duration")]
                if timed:
                    chosen = min(timed, key=lambda e: abs(e["duration"] - expected_duration_s))
        return f"https://www.youtube.com/watch?v={chosen['id']}"

    def _loose_pick(self, candidates, expected_duration_s):
        """Opt-in fallback (Settings: "use closest result if no match").

        When strict title/artist matching finds nothing, return the
        duration-closest candidate (or the top result if durations are
        missing). Recovers cross-script matches the ascii title filter can
        never make - e.g. a Latin Spotify title vs a Greek/Cyrillic/CJK
        youtube title. Trades the never-grab-the-wrong-audio guarantee for
        coverage, which is why the caller only reaches here when loose_match
        is on (off by default).
        """
        if not candidates:
            return None
        chosen = candidates[0]
        if expected_duration_s:
            timed = [e for e in candidates if e.get("duration")]
            if timed:
                chosen = min(timed, key=lambda e: abs(e["duration"] - expected_duration_s))
        log.warning("loose match (no confident title/artist match): selected %s", chosen["id"])
        return f"https://www.youtube.com/watch?v={chosen['id']}"

    def download_track_audio(
        self,
        search_query,
        destination,
        expected_duration_s=None,
        expected_title=None,
        expected_artists=None,
    ):
        # Check for FFmpeg first
        ffmpeg_path = get_ffmpeg_path()
        if not ffmpeg_path:
            raise RuntimeError(
                "FFmpeg not found! Install via: brew install ffmpeg (macOS) "
                "or apt install ffmpeg (Linux)"
            )

        fmt = self.audio_format if self.audio_format in SUPPORTED_FORMATS else "mp3"
        ext = SUPPORTED_FORMATS[fmt]["ext"]
        is_lossy = SUPPORTED_FORMATS[fmt]["lossy"]

        base, _ = os.path.splitext(destination)
        output_template = base + ".%(ext)s"
        postprocessor = {
            "key": "FFmpegExtractAudio",
            "preferredcodec": fmt,
        }
        if is_lossy:
            postprocessor["preferredquality"] = self.audio_quality

        ydl_opts = {
            "format": "bestaudio/best",
            "quiet": True,
            "no_warnings": True,
            "outtmpl": output_template,
            "ffmpeg_location": ffmpeg_path,
            "retries": 5,
            "socket_timeout": 15,
            "concurrent_fragment_downloads": 4,
            "ignoreerrors": True,
            "postprocessors": [postprocessor],
        }

        expected_path = base + "." + ext

        # Primary query (widened to 5 results), then a simplified fallback if
        # the first pass produced nothing. For each, pick the duration-closest
        # candidate (avoids grabbing the music video / wrong edit) and download
        # that specific video. Success is decided purely by whether an audio
        # file landed on disk, so a search with no playable source fails loudly
        # instead of silently reporting a path that does not exist.
        queries = [self._widen_search(search_query)]
        fallback = self._simplify_search(search_query)
        if fallback not in queries:
            queries.append(fallback)

        # Two download attempts per resolved video: the default (web) client
        # first (unchanged happy path), then a fallback that forces the
        # non-web player clients. YouTube increasingly bot-challenges the web
        # client per-IP, and the alternate clients (android/ios/tv) use
        # different endpoints that often still serve audio. The fallback only
        # runs when the first attempt produced no file, so a working download
        # is byte-for-byte the same as before.
        fallback_opts = {
            **ydl_opts,
            "extractor_args": {
                "youtube": {"player_client": ["android", "ios", "tv", "web_safari"]}
            },
        }
        attempts = [("default", ydl_opts), ("fallback", fallback_opts)]

        for query in queries:
            video_url = self._select_youtube_match(
                query,
                expected_duration_s,
                expected_title=expected_title,
                expected_artists=expected_artists,
            )
            if not video_url:
                continue
            for label, opts in attempts:
                # per-attempt bridge captures yt-dlp's own error even when
                # ignoreerrors swallows it (no exception, no file)
                ytlog = _YtdlpLog()
                try:
                    with YoutubeDL({**opts, "logger": ytlog}) as ydl:
                        ydl.extract_info(video_url, download=True)
                except Exception as exc:
                    log.warning(
                        "download attempt (%s) failed for %s: %s",
                        label,
                        video_url,
                        str(exc)[:300],
                    )
                else:
                    if not os.path.exists(expected_path):
                        # the silent case: yt-dlp produced no file without
                        # raising; the bridge holds the real reason
                        reason = (ytlog.last_error or "no error reported by yt-dlp").strip()
                        log.warning(
                            "download attempt (%s) produced no file for %s: %s",
                            label,
                            video_url,
                            reason[:300],
                        )
                if os.path.exists(expected_path):
                    if label != "default":
                        log.info("recovered via %s player clients", label)
                    return expected_path

        log.debug("no playable audio landed for query set %r", queries)
        raise RuntimeError("no playable audio source found on YouTube for this track")

    def download_http_file(self, url, destination):
        response = self.session.get(url, stream=True, timeout=60)
        response.raise_for_status()
        total = int(response.headers.get("content-length", 0))
        downloaded = 0
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        with open(destination, "wb") as handle:
            for chunk in response.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                handle.write(chunk)
                downloaded += len(chunk)
                if total:
                    progress = int(downloaded / total * 100)
                    self.dlprogress_signal.emit(progress)
        return destination

    def _download_one_track(self, track, playlist_folder_path, default_cover_url, track_num=0):
        """Download a single track. Runs inside a ThreadPoolExecutor worker.

        Returns None on success, the track title on failure (for _failed_tracks).
        Qt signals emitted here cross thread boundaries via queued connections,
        which is safe.

        In parallel mode (self._parallel_mode), per-track UI noise (song_meta
        preview, per-byte progress) is suppressed because those widgets are
        single-track and would flicker with N workers in flight. add_song_meta
        still fires so ID3 tags + cover art get written to every mp3.

        track_num (1-based) is passed through to song_meta so the ID3 TRCK
        frame can be populated for playlist ordering.
        """
        if self.is_cancelled():
            return None

        track_title = track.title
        artists = track.artists
        sanitized_title = self.sanitize_text(track_title)
        sanitized_artists = self.sanitize_text(artists)

        if self.include_track_number:
            filename = f"{track_num:02d}. {sanitized_title} - {sanitized_artists}.mp3"
        else:
            filename = f"{sanitized_title} - {sanitized_artists}.mp3"

        filepath = os.path.join(playlist_folder_path, cap_filename(filename))

        # Filename collision guard: two different tracks can sanitize to the
        # same filename (e.g. "Café" vs "Cafe"). Under parallel downloads the
        # naive os.path.exists check has a TOCTOU race where both workers pass
        # the check and clobber each other's files. Claim the filename via a
        # lock; if taken, suffix with track id to de-dupe.
        with self._filename_lock:
            if filepath in self._in_flight_files:
                if self.include_track_number:
                    filename = (
                        f"{track_num:02d}. {sanitized_title} - {sanitized_artists} [{track.id}].mp3"
                    )
                else:
                    filename = f"{sanitized_title} - {sanitized_artists} [{track.id}].mp3"

                filepath = os.path.join(
                    playlist_folder_path,
                    cap_filename(filename),
                )
            self._in_flight_files.add(filepath)

        # Per-track cover enrichment. Spotify's playlist embed trackList does
        # not include per-track cover URLs at all, so without this enrichment
        # every track ends up falling back to default_cover_url (the playlist
        # cover). That's the reported bug: "all 300 songs have the same cover".
        # Fix: when cover_url is missing, fetch /embed/track/{id} which has
        # the real visualIdentity.image. The request runs synchronously
        # inside the worker before the YouTube search, so it adds roughly
        # 100-300ms per track in sequential mode. In parallel mode that
        # per-track cost overlaps with downloads running in other workers,
        # so aggregate wall-clock impact on a full playlist stays small.
        cover_url = track.cover_url
        release_date = track.release_date or ""
        if (
            not cover_url
            and track.id
            and self.spotifydown_api is not None
            and not self.is_cancelled()
        ):
            try:
                enriched = self.spotifydown_api.get_track(track.id)
                if enriched:
                    if enriched.cover_url:
                        cover_url = enriched.cover_url
                    if not release_date and enriched.release_date:
                        release_date = enriched.release_date
            except SpotifyDownAPIError as exc:
                log.debug("cover enrichment failed for '%s': %s", track_title, exc)

        cover_url = cover_url or default_cover_url
        album_name = track.album or ""

        song_meta = {
            "title": track_title,
            "artists": artists,
            "album": album_name,
            "releaseDate": release_date,
            "cover": cover_url or "",
            "file": filepath,
            "trackNumber": track_num,
        }

        # Emit song_meta so the preview panel shows the current track. With
        # multiple workers running, this label races between workers and ends
        # up showing whichever track most recently started, which is fine
        # (and better than a blank panel).
        self.song_meta.emit(dict(song_meta))

        try:
            if os.path.exists(filepath):
                self._record_in_manifest(track.id, filepath)
                self.add_song_meta.emit(song_meta)
                self._finish_track_ui(ok=True)
                return None

            search_query = f"ytsearch1:{track_title} {artists} audio"
            expected_dur = (track.duration_ms / 1000) if track.duration_ms else None
            try:
                final_path = self.download_track_audio(
                    search_query,
                    filepath,
                    expected_duration_s=expected_dur,
                    expected_title=track_title,
                    expected_artists=artists,
                )
            except Exception as error_status:
                error_msg = self._get_user_friendly_error(error_status, track_title)
                self.error_signal.emit(error_msg)
                # concise reason at WARNING (the per-attempt yt-dlp reason is
                # already logged above); full traceback only when verbose
                log.warning("track failed: '%s': %s", track_title, str(error_status)[:200])
                log.debug("track failure traceback for '%s'", track_title, exc_info=True)
                with self._failed_lock:
                    self._failed_tracks.append(track_title)
                self._finish_track_ui(ok=False)
                return track_title

            if not final_path or not os.path.exists(final_path):
                self.error_signal.emit(f"'{track_title}' - download failed")
                log.warning(
                    "track produced no audio file (no confident match or blocked): '%s'",
                    track_title,
                )
                with self._failed_lock:
                    self._failed_tracks.append(track_title)
                self._finish_track_ui(ok=False)
                return track_title

            self._record_in_manifest(track.id, final_path)
            song_meta["file"] = final_path
            self.add_song_meta.emit(song_meta)
            self._finish_track_ui(ok=True)
            return None
        finally:
            with self._filename_lock:
                self._in_flight_files.discard(filepath)

    def _finish_track_ui(self, ok: bool) -> None:
        """Update counter + progress bar after a track completes or fails."""
        self.increment_counter()
        if self._parallel_mode and self._total_tracks > 0:
            # Aggregate progress across all workers: show how many tracks are
            # done as a percentage. Avoids the N-workers-jittering-one-bar
            # problem where per-byte emits from 4 downloads make the bar jump.
            pct = int(self.counter / self._total_tracks * 100)
            self.dlprogress_signal.emit(min(pct, 100))
        elif ok:
            self.dlprogress_signal.emit(100)

    def _load_manifest(self, folder: str) -> set:
        """Load the set of track IDs already downloaded into `folder`.

        The manifest is a JSON-lines file inside the folder; each line is a
        `{"id", "file"}` record. Entries whose file is missing are ignored so
        a track the user deleted re-downloads. Returns the set of valid IDs
        and arms `_manifest_path` for incremental appends during this run.
        """
        import json

        path = os.path.join(folder, MANIFEST_FILENAME)
        self._manifest_path = path
        done: set[str] = set()
        if not os.path.exists(path):
            return done
        try:
            with open(path, encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except ValueError:
                        continue
                    track_id = record.get("id")
                    filename = record.get("file")
                    if track_id and filename and os.path.exists(os.path.join(folder, filename)):
                        done.add(track_id)
        except OSError:
            return set()
        return done

    def _record_in_manifest(self, track_id, filepath: str) -> None:
        """Append a completed track to the manifest (thread-safe).

        Append-only JSON-lines so recording a track is O(1) regardless of how
        large the playlist is. Failures are swallowed: the manifest is an
        optimization for resuming, never a hard dependency of a download.
        """
        if not track_id or not self._manifest_path:
            return
        import json

        record = json.dumps({"id": track_id, "file": os.path.basename(filepath)})
        with self._manifest_lock:
            try:
                with open(self._manifest_path, "a", encoding="utf-8") as handle:
                    handle.write(record + "\n")
            except OSError:
                pass

    def scrape_playlist(self, spotify_playlist_link, music_folder):
        # Reset mutable state so repeat invocations on the same scraper
        # instance don't carry stale counters or failure lists.
        with self._counter_lock:
            self.counter = 0
        with self._failed_lock:
            self._failed_tracks.clear()
        with self._filename_lock:
            self._in_flight_files.clear()
        self._parallel_mode = False
        self._total_tracks = 0

        # A playlist or an album both flow through here. detect_spotify_url_type
        # returns ("playlist"|"album", id); albums reuse the same embed-parsing
        # path with the album embed endpoint (closes #38).
        content_type, playlist_id = detect_spotify_url_type(spotify_playlist_link)
        if content_type not in ("playlist", "album"):
            raise ValueError("Expected a playlist or album URL")
        self.PlaylistID.emit(playlist_id)

        # Check cancel before doing any network work. Large playlists can
        # spend real time inside iter_playlist_tracks doing spclient + per
        # track embed fetches; if the user already clicked stop we shouldn't
        # bother.
        if self.is_cancelled():
            self.PlaylistCompleted.emit("Download cancelled")
            return

        try:
            spotify_api = self.ensure_spotifydown_api()
        except SpotifyDownAPIError as exc:
            raise RuntimeError(str(exc)) from exc

        metadata = spotify_api.get_playlist_metadata(playlist_id, content_type=content_type)
        playlist_display_name = self.format_playlist_name(metadata)
        self.song_Album.emit(playlist_display_name)

        playlist_folder_path = self.prepare_playlist_folder(music_folder, playlist_display_name)

        # Resume support: skip tracks already downloaded in a previous run of
        # this folder before fetching their (rate-limited) metadata, so a huge
        # playlist can be finished across multiple sessions (closes #40).
        already_done = self._load_manifest(playlist_folder_path)
        if already_done:
            self.error_signal.emit(
                f"Resuming: skipping {len(already_done)} already-downloaded track(s)"
            )

        # Materialize the generator into a list. iter_playlist_tracks is a
        # generator and generators are not thread-safe. Consuming it upfront
        # also lets us pick the right worker count based on track count.
        # Cancel is checked between yields so very large playlists (where
        # iter_playlist_tracks issues hundreds of spclient + per-track embed
        # requests serially) can abort mid-fetch instead of waiting through
        # the full window before the stop button takes effect.
        expected_total = metadata.track_count or 0
        tracks: list = []
        for track in spotify_api.iter_playlist_tracks(
            playlist_id, content_type=content_type, skip_ids=already_done
        ):
            if self.is_cancelled():
                break
            tracks.append(track)
            if expected_total and len(tracks) % 10 == 0:
                self.error_signal.emit(
                    f"Fetching track metadata ({len(tracks)} of {expected_total})..."
                )
        self._total_tracks = len(tracks)

        if self.is_cancelled():
            self.PlaylistCompleted.emit("Download cancelled")
            return

        self.Resetprogress_signal.emit(0)

        # Small playlists don't benefit from parallelism. Keep 1 worker for
        # playlists under 3 tracks to preserve the single-track UI feel.
        worker_count = 1 if len(tracks) < 3 else min(self.MAX_WORKERS, len(tracks))
        self._parallel_mode = worker_count > 1

        log.info(
            "%s scrape: name=%r id=%s tracks=%d (resume-skipped %d) mode=%s workers=%d fmt=%s/%s",
            content_type,
            playlist_display_name,
            playlist_id,
            len(tracks),
            len(already_done),
            "parallel" if self._parallel_mode else "sequential",
            worker_count,
            self.audio_format,
            self.audio_quality,
        )

        # Prefer the canonical Spotify playlist position when the API gave
        # one (it does for any playlist whose tracks went through the
        # spclient fallback, which is the only place enumerate-of-yield-
        # order would diverge from playlist order). Fall back to enumerate
        # index for albums + small playlists where every track came from
        # the embed page already in order. Closes #51.
        def _track_num_for(track, idx):
            return track.position if getattr(track, "position", None) else idx

        if worker_count == 1:
            for idx, track in enumerate(tracks, start=1):
                if self.is_cancelled():
                    break
                # Reset the per-track progress bar at the top of each iteration
                # so the single-track UI behaves the way it always has.
                self.Resetprogress_signal.emit(0)
                self._download_one_track(
                    track,
                    playlist_folder_path,
                    metadata.cover_url,
                    track_num=_track_num_for(track, idx),
                )
        else:
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
                    futures = [
                        executor.submit(
                            self._download_one_track,
                            track,
                            playlist_folder_path,
                            metadata.cover_url,
                            _track_num_for(track, idx),
                        )
                        for idx, track in enumerate(tracks, start=1)
                    ]
                    for future in concurrent.futures.as_completed(futures):
                        if self.is_cancelled():
                            # Cancel remaining futures that haven't started
                            # yet. In-flight downloads check is_cancelled at
                            # their own top and return early.
                            for f in futures:
                                f.cancel()
                            break
                        try:
                            future.result()
                        except Exception as exc:
                            # _download_one_track handles its own errors; this is
                            # only framework-level fallout (a worker crashed hard).
                            log.error("unexpected worker error", exc_info=exc)
                            self.error_signal.emit(f"Unexpected worker error: {exc}")
            finally:
                # Reset parallel_mode only after the executor has fully shut
                # down (context manager exit waits on in-flight workers). If
                # we reset inside the `with`, workers that are still running
                # after a break would observe False and start emitting
                # single-track UI signals.
                self._parallel_mode = False

        if self.is_cancelled():
            log.info("scrape cancelled by user (%d done before cancel)", self.counter)
            self.PlaylistCompleted.emit("Download cancelled")
            return

        # Report completion with failed track count
        ok = max(self._total_tracks - len(self._failed_tracks), 0)
        if self._failed_tracks:
            log.info("scrape done: %d ok, %d failed", ok, len(self._failed_tracks))
            log.info("failed tracks: %s", " | ".join(self._failed_tracks))
            self.PlaylistCompleted.emit(f"Done! {len(self._failed_tracks)} track(s) failed")
        else:
            log.info("scrape done: %d ok, 0 failed", self._total_tracks)
            self.PlaylistCompleted.emit("Download Complete!")

    def returnSPOT_ID(self, link):
        """Extract playlist ID from Spotify URL."""
        return extract_playlist_id(link)

    def scrape_track(self, spotify_track_link, music_folder):
        """Download a single track from Spotify."""
        url_type, track_id = detect_spotify_url_type(spotify_track_link)
        if url_type != "track":
            raise ValueError("Expected a track URL")

        try:
            spotify_api = self.ensure_spotifydown_api()
        except SpotifyDownAPIError as exc:
            raise RuntimeError(str(exc)) from exc

        track = spotify_api.get_track(track_id)
        log.info(
            "single-track scrape: %r by %r id=%s fmt=%s/%s",
            track.title,
            track.artists,
            track_id,
            self.audio_format,
            self.audio_quality,
        )
        self.song_Album.emit("Single Track Download")

        if not os.path.exists(music_folder):
            os.makedirs(music_folder)

        self.Resetprogress_signal.emit(0)

        track_title = track.title
        artists = track.artists
        sanitized_title = self.sanitize_text(track_title)
        sanitized_artists = self.sanitize_text(artists)
        filename = f"{sanitized_title} - {sanitized_artists}.mp3"
        filepath = os.path.join(music_folder, cap_filename(filename))

        album_name = track.album or ""
        release_date = track.release_date or ""
        cover_url = track.cover_url

        song_meta = {
            "title": track_title,
            "artists": artists,
            "album": album_name,
            "releaseDate": release_date,
            "cover": cover_url or "",
            "file": filepath,
            "trackNumber": 1,
        }

        self.song_meta.emit(dict(song_meta))

        if os.path.exists(filepath):
            self.add_song_meta.emit(song_meta)
            self.increment_counter()
            self.PlaylistCompleted.emit("Track already exists!")
            return

        # Download via YouTube search
        search_query = f"ytsearch1:{track_title} {artists} audio"
        expected_dur = (track.duration_ms / 1000) if track.duration_ms else None
        try:
            final_path = self.download_track_audio(
                search_query, filepath, expected_duration_s=expected_dur
            )
        except Exception as error_status:
            error_msg = self._get_user_friendly_error(error_status, track_title)
            log.error("single-track download failed: '%s'", track_title, exc_info=True)
            self.PlaylistCompleted.emit(error_msg)
            return

        if not final_path or not os.path.exists(final_path):
            log.warning("single-track produced no audio file: '%s'", track_title)
            self.PlaylistCompleted.emit("Download failed - no audio file produced")
            return

        song_meta["file"] = final_path
        self.add_song_meta.emit(song_meta)
        self.increment_counter()
        self.dlprogress_signal.emit(100)
        self.PlaylistCompleted.emit("Download Complete!")

    def increment_counter(self):
        with self._counter_lock:
            self.counter += 1
            current = self.counter
        self.count_updated.emit(current)  # Emit the signal with the updated count


# Scraper Thread
class ScraperThread(QThread):
    progress_update = pyqtSignal(str)

    def __init__(
        self,
        spotify_link,
        music_folder=None,
        cancel_event: threading.Event | None = None,
        *,
        audio_format: str = "mp3",
        audio_quality: str = "192",
        include_track_number: bool = False,
        loose_match: bool = False,
    ):
        super().__init__()
        self.spotify_link = spotify_link
        self.music_folder = music_folder or os.path.join(os.getcwd(), "music")
        self._cancel_event = cancel_event or threading.Event()
        self.scraper = MusicScraper(
            cancel_event=self._cancel_event,
            audio_format=audio_format,
            audio_quality=audio_quality,
            include_track_number=include_track_number,
            loose_match=loose_match,
        )

    def request_cancel(self):
        """Request cancellation of the download."""
        self._cancel_event.set()

    def run(self):
        self.progress_update.emit("Scraping started...")
        try:
            # Detect URL type and handle accordingly
            url_type, _ = detect_spotify_url_type(self.spotify_link)
            if url_type == "track":
                self.scraper.scrape_track(self.spotify_link, self.music_folder)
            else:
                self.scraper.scrape_playlist(self.spotify_link, self.music_folder)
            self.progress_update.emit("Scraping completed.")
        except Exception as e:
            log.exception("scrape failed for %s", self.spotify_link)
            self.progress_update.emit(f"{e}")


def _fetch_cover_bytes(url: str) -> bytes | None:
    """Download cover image bytes, returning None on any failure."""
    if not url:
        return None
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200 and resp.content:
            return resp.content
    except (requests.RequestException, OSError) as exc:
        log.debug("cover fetch failed: %s", exc)
    return None


def _detect_image_mime(data: bytes) -> str:
    """Return the MIME string for image bytes, sniffed from magic numbers.

    Spotify currently serves JPEG covers; this function exists so a future
    switch to PNG (or a mid-flight content-type change) doesn't silently
    produce broken cover-art frames mis-tagged as JPEG.

    ref: JPEG magic ff d8 ff (any JFIF/Exif variant), per ISO/IEC 10918-1
    ref: PNG signature 89 50 4e 47 0d 0a 1a 0a, per W3C PNG spec section 5.2
    """
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    return "image/jpeg"  # safe default; Spotify has served JPEG since 2015


def _write_metadata_mp3(filename: str, tags: dict, cover_bytes: bytes | None) -> None:
    """Write ID3 tags + embedded cover art to an MP3.

    Tags and the APIC cover frame are written as ID3v2.3 with UTF-16 text
    encoding instead of mutagen's v2.4 / UTF-8 default. v2.3 + UTF-16 is the
    lowest common denominator that's understood by older iTunes, Windows
    Media Player, most car head-units, and stock Android players, none of
    which read v2.4 APIC frames reliably (closes #46).

    ref: ID3v2.3 spec section 3.3 (only encoding values $00 ISO-8859-1
         and $01 Unicode UTF-16+BOM are defined) https://id3.org/id3v2.3.0
    ref: ID3v2.4 spec adds $02 UTF-16BE and $03 UTF-8 (which is what
         mutagen writes by default) https://id3.org/id3v2.4.0-frames
    ref: mutagen `update_to_v23()` downgrades any UTF-8 frames to UTF-16
         before saving as v2.3 https://mutagen.readthedocs.io/en/latest/api/id3.html
    """
    audio = EasyID3(filename)
    audio["title"] = tags.get("title", "")
    audio["artist"] = tags.get("artists", "")
    audio["album"] = tags.get("album", "")
    audio["date"] = tags.get("releaseDate", "")
    track_num = tags.get("trackNumber") or 0
    if track_num:
        audio["tracknumber"] = str(track_num)
    # EasyID3.save() defaults to v2.4 + UTF-8. Passing v2_version=3 tells
    # mutagen to downgrade text frames to a v2.3-allowed encoding (UTF-16
    # with BOM for non-ASCII, Latin-1 for ASCII) before writing.
    audio.save(v2_version=3)
    if cover_bytes:
        id3 = ID3(filename)
        mime = _detect_image_mime(cover_bytes)
        # encoding=1 (UTF-16+BOM) is the only Unicode encoding v2.3 defines.
        # type=3 is "Cover (front)" per the v2.3 APIC enum.
        id3.add(APIC(encoding=1, mime=mime, type=3, desc="Cover", data=cover_bytes))
        id3.update_to_v23()
        id3.save(v2_version=3)


def _write_metadata_m4a(filename: str, tags: dict, cover_bytes: bytes | None) -> None:
    """Write iTunes atom tags + embedded cover art to an M4A/MP4.

    iTunes atoms (`covr`, `\xa9nam`, etc.) are a stable, version-less spec
    used by every MP4-aware player. The only knob worth getting right is
    the cover-art image format, which we sniff so a future PNG cover from
    Spotify doesn't get mis-tagged as JPEG.

    ref: mutagen MP4Tags atom keys (`\xa9nam`/`\xa9ART`/`\xa9alb`/`\xa9day`/
         `trkn`/`covr`) and MP4Cover.FORMAT_JPEG/PNG, which is the spec we
         write against https://mutagen.readthedocs.io/en/latest/api/mp4.html
    """
    from mutagen.mp4 import MP4, MP4Cover

    audio = MP4(filename)
    audio["\xa9nam"] = tags.get("title", "")
    audio["\xa9ART"] = tags.get("artists", "")
    audio["\xa9alb"] = tags.get("album", "")
    date = tags.get("releaseDate", "")
    if date:
        audio["\xa9day"] = date
    track_num = tags.get("trackNumber") or 0
    if track_num:
        audio["trkn"] = [(int(track_num), 0)]
    if cover_bytes:
        mime = _detect_image_mime(cover_bytes)
        fmt = MP4Cover.FORMAT_PNG if mime == "image/png" else MP4Cover.FORMAT_JPEG
        audio["covr"] = [MP4Cover(cover_bytes, imageformat=fmt)]
    audio.save()


def _write_metadata_flac(filename: str, tags: dict, cover_bytes: bytes | None) -> None:
    """Write Vorbis comments + embedded cover art to a FLAC.

    FLAC's Picture block carries an explicit MIME string, so we sniff the
    image type and pass it through. Vorbis comments are always UTF-8 and
    universally supported, so nothing else is version-sensitive here.

    ref: FLAC METADATA_BLOCK_PICTURE format spec
         https://xiph.org/flac/format.html#metadata_block_picture
    """
    from mutagen.flac import FLAC, Picture

    audio = FLAC(filename)
    audio["title"] = tags.get("title", "")
    audio["artist"] = tags.get("artists", "")
    audio["album"] = tags.get("album", "")
    date = tags.get("releaseDate", "")
    if date:
        audio["date"] = date
    track_num = tags.get("trackNumber") or 0
    if track_num:
        audio["tracknumber"] = str(track_num)
    if cover_bytes:
        # add_picture() appends; clear first so a re-tag doesn't stack duplicate covers
        audio.clear_pictures()
        pic = Picture()
        pic.type = 3  # Front cover
        pic.mime = _detect_image_mime(cover_bytes)
        pic.desc = "Cover"
        pic.data = cover_bytes
        audio.add_picture(pic)
    audio.save()


_METADATA_WRITERS = {
    ".mp3": _write_metadata_mp3,
    ".m4a": _write_metadata_m4a,
    ".flac": _write_metadata_flac,
}


class WritingMetaTagsThread(QThread):
    tags_success = pyqtSignal(str)

    def __init__(self, tags, filename):
        super().__init__()
        self.tags = tags
        self.filename = filename

    def run(self):
        """Write tags + cover art synchronously, dispatching on file extension.

        Each container uses a different tag system (ID3 for mp3, iTunes atoms
        for m4a, Vorbis comments for flac). Opus/WAV are skipped with a log
        line; those formats have limited or no standard cover-art story that
        would repay the extra dependency surface for this project's scope.
        """
        try:
            log.info("writing tags: %s", self.filename)
            ext = os.path.splitext(self.filename)[1].lower()
            writer = _METADATA_WRITERS.get(ext)
            if writer is None:
                self.tags_success.emit("Tags skipped (unsupported container)")
                return

            cover_bytes = _fetch_cover_bytes(self.tags.get("cover", ""))
            writer(self.filename, self.tags, cover_bytes)
            self.tags_success.emit("Tags added successfully")
        except Exception:
            log.error("tag write failed: %s", self.filename, exc_info=True)


class DownloadThumbnail(QThread):
    thumbnail_ready = pyqtSignal(bytes)  # Signal to safely update UI from main thread

    def __init__(self, url, main_UI):
        super().__init__()
        self.url = url
        self.main_UI = main_UI
        self.thumbnail_ready.connect(self._update_ui)

    def run(self):
        if not self.url:
            return
        try:
            response = requests.get(self.url, stream=True, timeout=10)
            if response.status_code == 200:
                self.thumbnail_ready.emit(response.content)
        except Exception as exc:
            log.debug("thumbnail fetch failed: %s", exc)

    def _update_ui(self, data):
        """Update UI from main thread via signal."""
        pic = QImage()
        pic.loadFromData(data)
        self.main_UI.CoverImg.setPixmap(QPixmap(pic))
        self.main_UI.CoverImg.show()


class SettingsDialog(QDialog):
    """Download folder + audio format + quality in one dialog."""

    def __init__(self, parent, config: dict):
        super().__init__(parent)
        self.setWindowTitle("Sunnify Settings")
        self.setModal(True)
        # min width so long macOS paths fit; height is sized at the end once hints exist
        self.setMinimumWidth(560)
        self._config = dict(config)

        from PyQt6.QtWidgets import QLabel, QLineEdit

        # QLineEdit (read-only) handles arbitrarily long paths cleanly: it
        # elides mid-path with horizontal scroll on focus, rather than
        # truncating and leaving the user guessing. Tooltip always shows the
        # full value.
        self._folder_label = QLineEdit(self._config.get("download_path") or "(not set)")
        self._folder_label.setReadOnly(True)
        self._folder_label.setFrame(False)
        self._folder_label.setCursorPosition(0)
        self._folder_label.setToolTip(self._folder_label.text())
        self._folder_label.setStyleSheet("QLineEdit { background: transparent; padding: 0; }")
        browse = QPushButton("Choose folder")
        browse.clicked.connect(self._choose_folder)

        folder_row = QHBoxLayout()
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
        current_q = self._config.get("quality", "192")
        self._quality_cb.setCurrentText(f"{current_q} kbps")
        self._on_format_change(self._format_cb.currentText())

        self._include_track_number_cb = QCheckBox()
        self._include_track_number_cb.setChecked(self._config.get("include_track_number", False))

        self._loose_match_cb = QCheckBox()
        self._loose_match_cb.setChecked(self._config.get("loose_match", False))

        # Per-setting QVBoxLayout block: each setting is a self-contained
        # vertical mini-layout owning its own height. QFormLayout was tried
        # earlier and wrapping hint labels got clipped because the row height
        # was computed from the (empty) label column rather than from the
        # word-wrapped value column. Owning the height per-block via QFrame
        # + QVBoxLayout + Preferred size policy lets each hint expand to
        # however many lines its text needs at the dialog's current width.
        from PyQt6.QtGui import QFontMetrics, QPalette
        from PyQt6.QtWidgets import QFrame, QSizePolicy

        # one list so the label column is measured from the longest label, not a magic width
        _settings = [
            (
                "Download folder:",
                folder_row,
                "Each playlist or album becomes its own folder inside this directory.",
            ),
            (
                "Audio format:",
                self._format_cb,
                "mp3 plays everywhere. m4a is smaller at the same quality. "
                "flac and wav are lossless (much larger files).",
            ),
            (
                "Audio quality:",
                self._quality_cb,
                "Applies to lossy formats only (mp3, m4a, opus). "
                "320 kbps is the highest quality these formats support.",
            ),
            (
                "Track number in filename:",
                self._include_track_number_cb,
                'Off → "Song - Artist.mp3".   On → "01. Song - Artist.mp3".   '
                "Files sort in playlist order in your file manager.",
            ),
            (
                "Use closest result if no match:",
                self._loose_match_cb,
                "Off (default): skips a track rather than risk the wrong audio. "
                "On: falls back to the closest result by length, which recovers "
                "songs whose YouTube title is in another script (Greek, Cyrillic, "
                "Korean) but may let an occasional cover or remix slip through.",
            ),
        ]
        _fm = QFontMetrics(self.font())
        LABEL_W = max(_fm.horizontalAdvance(lbl) for lbl, _, _ in _settings) + 8

        # muted palette text so hints stay readable on light (win/linux) and dark (mac) themes
        _fg = self.palette().color(QPalette.ColorRole.WindowText)
        _hint_color = f"rgba({_fg.red()}, {_fg.green()}, {_fg.blue()}, 175)"

        def _setting_block(label_text: str, control, hint_text: str) -> QFrame:
            container = QFrame()
            box = QVBoxLayout(container)
            box.setSpacing(4)
            box.setContentsMargins(0, 0, 0, 12)  # visual gap between settings

            # Top row: label + control side-by-side, label fixed-width so all
            # the controls in different blocks line up vertically.
            row = QHBoxLayout()
            row.setSpacing(10)
            row.setContentsMargins(0, 0, 0, 0)
            name = QLabel(label_text)
            name.setMinimumWidth(LABEL_W)
            name.setMaximumWidth(LABEL_W)
            name.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row.addWidget(name)
            if isinstance(control, QHBoxLayout):
                row.addLayout(control, 1)
            else:
                row.addWidget(control, 1)
            box.addLayout(row)

            # Hint below, indented to start under the control column so it
            # visually associates with the control rather than the label.
            if hint_text:
                hint = QLabel(hint_text)
                hint.setWordWrap(True)
                hint.setStyleSheet(f"color: {_hint_color}; font-size: 11px;")
                hint.setContentsMargins(LABEL_W + 12, 2, 4, 0)
                hint.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
                box.addWidget(hint)
            return container

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        # Gives users a one-click way to grab the log file to attach to a bug
        # report, without hunting through ~/Library/Logs or %LOCALAPPDATA%.
        open_logs = btns.addButton("Open logs folder", QDialogButtonBox.ButtonRole.ActionRole)
        open_logs.setToolTip(log_file_path())
        open_logs.clicked.connect(self._open_logs)

        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        for _label, _control, _hint in _settings:
            layout.addWidget(_setting_block(_label, _control, _hint))
        layout.addStretch(1)
        layout.addWidget(btns)

        # activate() resolves wrap heights before sizing so the tallest hint isn't clipped
        layout.activate()
        self.resize(620, self.sizeHint().height())

    def _open_logs(self):
        """Reveal the log folder in the OS file manager."""
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QDesktopServices

        log_dir = _log_dir()
        with contextlib.suppress(OSError):
            os.makedirs(log_dir, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(log_dir))

    def _choose_folder(self):
        start = (
            self._folder_label.text()
            if os.path.isdir(self._folder_label.text())
            else os.path.expanduser("~")
        )
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Download Folder",
            start,
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks,
        )
        if folder:
            # Only append "Sunnify" when the user picked a non-Sunnify folder,
            # otherwise re-selecting the existing destination creates nested
            # Sunnify/Sunnify/... paths.
            chosen = (
                folder
                if os.path.basename(folder.rstrip(os.sep)) == "Sunnify"
                else os.path.join(folder, "Sunnify")
            )
            self._folder_label.setText(chosen)
            self._folder_label.setCursorPosition(0)
            self._folder_label.setToolTip(chosen)

    def _on_format_change(self, fmt: str) -> None:
        """Lossless formats (flac/wav) ignore the bitrate selector."""
        is_lossy = SUPPORTED_FORMATS.get(fmt, {}).get("lossy", True)
        self._quality_cb.setEnabled(is_lossy)

    def result_config(self) -> dict:
        self._config["download_path"] = self._folder_label.text()
        self._config["format"] = self._format_cb.currentText()
        self._config["quality"] = self._quality_cb.currentText().split()[0]
        self._config["include_track_number"] = self._include_track_number_cb.isChecked()
        self._config["loose_match"] = self._loose_match_cb.isChecked()
        return self._config


class UpdateNotifier(QDialog):
    """Toast-style 'new version available' card. Static copy, dynamic versions,
    so there's no per-release content to maintain. Download opens the releases
    page (where the auto-generated changelog already lives)."""

    def __init__(self, parent, current: str, latest: str, url: str):
        super().__init__(parent)
        from PyQt6.QtGui import QColor, QFont, QFontMetrics
        from PyQt6.QtWidgets import QFrame, QLabel, QWidget

        self._url = url
        self.setWindowTitle("Update available")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setModal(True)
        self.setFont(QFont("Arial", 10))

        green, green_hover = "#1ED760", "#1FE968"
        cyan, purple = "rgba(80, 214, 255, 255)", "rgba(112, 32, 213, 255)"
        ink, mute = "#15151F", "#7A7A8C"

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 26, 28, 30)  # room for the drop shadow
        # fractional dpi under-measures the wrapped body and squeezes the card (#64)
        outer.setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)

        card = QFrame()
        card.setObjectName("card")
        card.setFixedWidth(430)
        card.setStyleSheet("QFrame#card{background:#FFFFFF;border-radius:18px;}")
        shadow = QGraphicsDropShadowEffect(blurRadius=48, xOffset=0, yOffset=16)
        shadow.setColor(QColor(20, 10, 40, 110))
        card.setGraphicsEffect(shadow)
        outer.addWidget(card)

        v = QVBoxLayout(card)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        header = QFrame()
        header.setObjectName("hdr")
        header.setStyleSheet(
            "QFrame#hdr{border-top-left-radius:18px;border-top-right-radius:18px;"
            f"background:qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1,"
            f"stop:0.23 {cyan}, stop:0.81 {purple});}}"
        )
        hv = QVBoxLayout(header)
        hv.setContentsMargins(26, 20, 26, 22)
        hv.setSpacing(0)  # gaps are set explicitly between rows below

        eyebrow = QLabel("UPDATE AVAILABLE")
        ef = QFont("Arial", 9, QFont.Weight.Bold)
        ef.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.5)
        eyebrow.setFont(ef)
        eyebrow.setStyleSheet("color: rgba(255,255,255,0.85);")
        hv.addWidget(eyebrow)
        hv.addSpacing(8)

        name = QLabel("Sunnify")
        nfont = QFont("Arial", 22, QFont.Weight.Bold)
        name.setFont(nfont)
        name.setStyleSheet("color: #FFFFFF;")
        # large bold glyphs exceed QLabel's tight default box; reserve full height
        name.setMinimumHeight(QFontMetrics(nfont).height() + 10)
        hv.addWidget(name)
        hv.addSpacing(10)  # clear gap so the 'y' descender never crowds the version line

        # current -> new, read left to right; new version brighter/bold to draw the eye
        prog = QLabel(
            f'<span style="color:rgba(255,255,255,0.8)">{current}</span>'
            "&nbsp;&nbsp;&#8594;&nbsp;&nbsp;"
            f'<span style="color:#FFFFFF;font-weight:bold">{latest}</span>'
        )
        pfont = QFont("Arial", 13)
        prog.setFont(pfont)
        prog.setMinimumHeight(QFontMetrics(pfont).height() + 6)
        hv.addWidget(prog)
        v.addWidget(header)

        body = QWidget()
        bv = QVBoxLayout(body)
        bv.setContentsMargins(26, 22, 26, 6)
        msg = QLabel(
            "A newer version of Sunnify is available. Download it from the "
            "releases page to get the latest fixes and improvements."
        )
        msg.setWordWrap(True)
        msg.setFont(QFont("Arial", 10))
        msg.setStyleSheet(f"color: {mute};")
        bv.addWidget(msg)
        v.addWidget(body)

        footer = QWidget()
        fv = QHBoxLayout(footer)
        fv.setContentsMargins(26, 8, 26, 22)
        fv.setSpacing(10)

        later = QPushButton("Remind me later")
        later.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        later.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        later.setFixedHeight(40)
        later.setStyleSheet(
            f"QPushButton{{background:transparent;color:{mute};border:none;}}"
            f"QPushButton:hover{{color:{ink};}}"
        )
        later.clicked.connect(self.reject)
        fv.addWidget(later)
        fv.addStretch(1)

        download = QPushButton("Download")
        download.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        download.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        download.setFixedSize(132, 40)
        download.setStyleSheet(
            f"QPushButton{{background:{green};color:white;border-radius:10px;}}"
            f"QPushButton:hover{{background:{green_hover};}}"
        )
        download.clicked.connect(self._open_releases)
        fv.addWidget(download)
        v.addWidget(footer)

    def _open_releases(self):
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QDesktopServices

        if not QDesktopServices.openUrl(QUrl(self._url)):
            log.warning("could not open releases page in browser: %s", self._url)
        self.accept()


class StarPromptNotifier(QDialog):
    """One-time 'star the repo' card, shown the moment the first song of the
    user's first download lands on disk (owner call: value is proven by a
    real file and the user is mid-wait; huge playlists never reach
    'complete' in one sitting, so completion was the wrong hook). Same card
    pattern as UpdateNotifier so it inherits the high-dpi behaviour verified
    for 2.0.13. Shown exactly once per install: the config flag is persisted
    before the dialog opens, so even a crash mid-dialog can never make it
    nag twice."""

    def __init__(self, parent):
        super().__init__(parent)
        from PyQt6.QtGui import QColor, QFont, QFontMetrics
        from PyQt6.QtWidgets import QFrame, QLabel, QWidget

        self._url = f"https://github.com/{GITHUB_REPO}"
        self.setWindowTitle("Enjoying Sunnify?")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setModal(True)
        self.setFont(QFont("Arial", 10))

        green, green_hover = "#1ED760", "#1FE968"
        cyan, purple = "rgba(80, 214, 255, 255)", "rgba(112, 32, 213, 255)"
        ink, mute = "#15151F", "#7A7A8C"

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 26, 28, 30)  # room for the drop shadow
        # fractional dpi under-measures the wrapped body and squeezes the card (#64)
        outer.setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)

        card = QFrame()
        card.setObjectName("card")
        card.setFixedWidth(430)
        card.setStyleSheet("QFrame#card{background:#FFFFFF;border-radius:18px;}")
        shadow = QGraphicsDropShadowEffect(blurRadius=48, xOffset=0, yOffset=16)
        shadow.setColor(QColor(20, 10, 40, 110))
        card.setGraphicsEffect(shadow)
        outer.addWidget(card)

        v = QVBoxLayout(card)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        header = QFrame()
        header.setObjectName("hdr")
        header.setStyleSheet(
            "QFrame#hdr{border-top-left-radius:18px;border-top-right-radius:18px;"
            f"background:qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1,"
            f"stop:0.23 {cyan}, stop:0.81 {purple});}}"
        )
        hv = QVBoxLayout(header)
        hv.setContentsMargins(26, 20, 26, 22)
        hv.setSpacing(0)  # gaps are set explicitly between rows below

        eyebrow = QLabel("FIRST SONG DOWNLOADED")
        ef = QFont("Arial", 9, QFont.Weight.Bold)
        ef.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.5)
        eyebrow.setFont(ef)
        eyebrow.setStyleSheet("color: rgba(255,255,255,0.85);")
        hv.addWidget(eyebrow)
        hv.addSpacing(8)

        name = QLabel("Enjoying Sunnify?")
        nfont = QFont("Arial", 22, QFont.Weight.Bold)
        name.setFont(nfont)
        name.setStyleSheet("color: #FFFFFF;")
        # large bold glyphs exceed QLabel's tight default box; reserve full height
        name.setMinimumHeight(QFontMetrics(nfont).height() + 10)
        hv.addWidget(name)
        hv.addSpacing(6)  # descender room; 'j'/'y'/'g' tails clip at 1.5x without it
        v.addWidget(header)

        body = QWidget()
        bv = QVBoxLayout(body)
        bv.setContentsMargins(26, 22, 26, 6)
        msg = QLabel(
            "A star on GitHub keeps this project alive - it's how new people "
            "find Sunnify, and it takes five seconds. This asks once and never "
            "again."
        )
        msg.setWordWrap(True)
        msg.setFont(QFont("Arial", 10))
        msg.setStyleSheet(f"color: {mute};")
        bv.addWidget(msg)
        v.addWidget(body)

        footer = QWidget()
        fv = QHBoxLayout(footer)
        fv.setContentsMargins(26, 8, 26, 22)
        fv.setSpacing(10)

        later = QPushButton("Maybe later")
        later.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        later.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        later.setFixedHeight(40)
        # pad right so the invisible hit area matches the other card's dismiss
        later.setStyleSheet(
            f"QPushButton{{background:transparent;color:{mute};border:none;"
            "text-align:left;padding-right:32px;}"
            f"QPushButton:hover{{color:{ink};}}"
        )
        later.clicked.connect(self.reject)
        fv.addWidget(later)
        fv.addStretch(1)

        star = QPushButton("Star on GitHub")
        star.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        sfont = QFont("Arial", 10, QFont.Weight.Bold)
        star.setFont(sfont)
        star.setFixedHeight(40)
        # metrics-derived width; a fixed box clips when linux substitutes arial
        star.setMinimumWidth(QFontMetrics(sfont).horizontalAdvance("Star on GitHub") + 44)
        star.setStyleSheet(
            f"QPushButton{{background:{green};color:white;border-radius:10px;"
            "padding-left:18px;padding-right:18px;}"
            f"QPushButton:hover{{background:{green_hover};}}"
        )
        star.clicked.connect(self._open_repo)
        fv.addWidget(star)
        v.addWidget(footer)

    def _open_repo(self):
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QDesktopServices

        if not QDesktopServices.openUrl(QUrl(self._url)):
            log.warning("could not open repo page in browser: %s", self._url)
        self.accept()


# Main Window
class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        """MainWindow constructor"""
        super().__init__()
        self.setupUi(self)
        # let the options row size to its content so "Add Meta Tags" isn't clipped
        # by the .ui's fixed-width container (varies with font/locale/dpi)
        self.horizontalLayoutWidget_5.adjustSize()

        # Load persisted user config so format/quality/folder survive restarts
        self._config = load_config()
        self.download_path = self._config.get("download_path") or self._get_default_download_path()
        self._download_path_set = bool(self._config.get("download_path"))
        self._active_threads = []  # Keep references to running threads to prevent GC crashes
        self._is_downloading = False  # Track download state for stop button
        self._cancel_event = threading.Event()  # Event for cooperative thread cancellation

        self.SONGINFORMATION.setGraphicsEffect(
            QGraphicsDropShadowEffect(blurRadius=25, xOffset=2, yOffset=2)
        )
        self.PlaylistLink.returnPressed.connect(self.on_returnButton)
        self.DownloadBtn.clicked.connect(self.on_returnButton)

        self.showPreviewCheck.stateChanged.connect(self.show_preview)

        self.Closed.clicked.connect(self.exitprogram)
        self.Select_Home.clicked.connect(self.Linkedin)
        self.SettingsBtn.clicked.connect(self.open_settings)

        # Hide the Album row in the preview panel: Spotify's unauthenticated
        # embed endpoints do not expose album name anywhere we can reach it,
        # so the field would always be blank. A missing row reads better than
        # a permanently empty label.
        self.label_8.hide()
        self.AlbumText.hide()

        # check for a newer release in the background; fail-silent, shows a toast only if found
        self._update_thread = UpdateCheckThread(__version__)
        self._update_thread.update_available.connect(self._show_update_notifier)
        self._active_threads.append(self._update_thread)
        self._update_thread.start()

    @pyqtSlot(str, str)
    def _show_update_notifier(self, latest: str, url: str):
        if QApplication.activeModalWidget() is not None:
            # never stack on another toast; the check simply runs again next launch
            log.info("update notifier skipped: another modal dialog is active")
            return
        log.info("update available: %s -> %s; showing notifier", __version__, latest)
        UpdateNotifier(self, __version__, latest, url).exec()

    @pyqtSlot(int)
    def _maybe_show_star_prompt(self, count: int):
        """One-time star ask the moment the first song of the user's first
        run lands on disk. Skipped after a Stop (a beg right then reads as
        nagging). Deferred cases (update toast on screen) retry naturally
        when the next song lands - the flag only persists once the dialog
        actually shows, so the one shot is never burned silently."""
        if count < 1 or self._config.get("star_prompt_shown"):
            return
        if self._cancel_event.is_set():
            return
        if QApplication.activeModalWidget() is not None:
            # never stack on the update notifier; the next landed song retries
            log.info("star prompt deferred: another modal dialog is active")
            return
        # persist before showing so a crash mid-dialog can never re-prompt
        self._config["star_prompt_shown"] = True
        save_config(self._config)
        log.info("first song landed - showing one-time star prompt")
        StarPromptNotifier(self).exec()

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
            "Select Download Folder",
            os.path.expanduser("~"),
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks,
        )
        if folder:
            # Keep downloads contained in a "Sunnify" subfolder, but avoid
            # creating nested Sunnify/Sunnify/... paths when the user picked
            # a folder that's already named Sunnify.
            if os.path.basename(folder.rstrip(os.sep)) == "Sunnify":
                self.download_path = folder
            else:
                self.download_path = os.path.join(folder, "Sunnify")
            self._download_path_set = True
            self._config["download_path"] = self.download_path
            save_config(self._config)
            return True
        return False

    def open_settings(self):
        """Full settings dialog: folder + audio format + bitrate."""
        cfg_for_dialog = dict(self._config)
        cfg_for_dialog["download_path"] = self.download_path
        dialog = SettingsDialog(self, cfg_for_dialog)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new = dialog.result_config()
            if new.get("download_path"):
                self.download_path = new["download_path"]
                self._download_path_set = True
            self._config.update(
                {
                    "download_path": self.download_path,
                    "format": new.get("format", "mp3"),
                    "quality": new.get("quality", "192"),
                    "include_track_number": new.get("include_track_number", False),
                    "loose_match": new.get("loose_match", False),
                }
            )
            save_config(self._config)
            self.statusMsg.setText("Settings saved")

    @pyqtSlot()
    def on_returnButton(self):
        # If already downloading, stop the download
        if self._is_downloading:
            self._stop_download()
            return

        spotify_url = self.PlaylistLink.text().strip()
        if not spotify_url:
            self.statusMsg.setText("Please enter a Spotify URL")
            return

        # ALWAYS prompt for download location on first download
        if not self._download_path_set:
            self.statusMsg.setText("Select download location...")
            if not self._prompt_download_location():
                self.statusMsg.setText("Download cancelled - no folder selected")
                return

        # Verify the selected path is still writable
        if not self._ensure_download_path():
            self.statusMsg.setText("Cannot write to download folder")
            QMessageBox.warning(
                self,
                "Invalid Download Location",
                f"Cannot write to:\n{self.download_path}\n\nPlease select a different folder.",
            )
            if not self._prompt_download_location():
                return

        try:
            # Validate URL type
            url_type, _ = detect_spotify_url_type(spotify_url)
            self.statusMsg.setText(f"Detected: {url_type}")

            # Reset cancel event and set downloading state
            self._cancel_event = threading.Event()
            self._is_downloading = True
            self.DownloadBtn.setText("Stop")

            self.scraper_thread = ScraperThread(
                spotify_url,
                self.download_path,
                cancel_event=self._cancel_event,
                audio_format=self._config.get("format", "mp3"),
                audio_quality=self._config.get("quality", "192"),
                include_track_number=self._config.get("include_track_number", False),
                loose_match=self._config.get("loose_match", False),
            )
            self.scraper_thread.progress_update.connect(self.update_progress)
            self.scraper_thread.finished.connect(self.thread_finished)
            self.scraper_thread.scraper.song_Album.connect(self.update_AlbumName)
            self.scraper_thread.scraper.song_meta.connect(self.update_song_META)
            self.scraper_thread.scraper.add_song_meta.connect(self.add_song_META)
            self.scraper_thread.scraper.dlprogress_signal.connect(self.update_song_progress)
            self.scraper_thread.scraper.Resetprogress_signal.connect(self.Reset_song_progress)
            self.scraper_thread.scraper.PlaylistCompleted.connect(
                lambda x: self.statusMsg.setText(x)
            )
            self.scraper_thread.scraper.error_signal.connect(lambda x: self.statusMsg.setText(x))

            # Connect the count_updated signal to the update_counter slot
            self.scraper_thread.scraper.count_updated.connect(self.update_counter)
            # after update_counter so the label reads "1" before the prompt opens
            self.scraper_thread.scraper.count_updated.connect(self._maybe_show_star_prompt)

            self.scraper_thread.start()

        except ValueError as e:
            self.statusMsg.setText(str(e))
            self._is_downloading = False
            self.DownloadBtn.setText("Download")

    def _stop_download(self):
        """Stop the current download gracefully using cooperative cancellation."""
        self.statusMsg.setText("Stopping download...")
        self.DownloadBtn.setEnabled(False)

        # Signal cancellation via event (thread checks this periodically)
        self._cancel_event.set()

        if hasattr(self, "scraper_thread") and self.scraper_thread.isRunning():
            self.scraper_thread.request_cancel()
            # Thread will finish current track and exit; UI resets via thread_finished signal

    def thread_finished(self):
        """Reset UI state when download thread finishes."""
        self._is_downloading = False
        self.DownloadBtn.setText("Download")
        self.DownloadBtn.setEnabled(True)
        if hasattr(self, "scraper_thread"):
            self.scraper_thread.deleteLater()  # Clean up the thread properly

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
            self.ArtistNameText.setToolTip(artists_full)
            self.AlbumText.setText(song_meta.get("album", ""))
            self.SongName.setText(song_meta.get("title", ""))
            self.YearText.setText(song_meta.get("releaseDate", ""))

        self.MainSongName.setText(song_meta.get("title", "") + " - " + song_meta.get("artists", ""))
        # NOTE: Meta tags are written in add_song_META (after file exists), not here

    @pyqtSlot(dict)
    def add_song_META(self, song_meta):
        if self.AddMetaDataCheck.isChecked():
            meta_thread = WritingMetaTagsThread(song_meta, song_meta["file"])
            meta_thread.tags_success.connect(lambda x: self.statusMsg.setText(f"{x}"))
            self._active_threads.append(meta_thread)
            meta_thread.finished.connect(lambda: self._cleanup_thread(meta_thread))
            meta_thread.start()

    def _cleanup_thread(self, thread):
        """Remove finished thread from active list."""
        if thread in self._active_threads:
            self._active_threads.remove(thread)

    @pyqtSlot(str)
    def update_AlbumName(self, AlbumName):
        self.AlbumName.setText("Playlist Name : " + AlbumName)

    @pyqtSlot(int)
    def update_counter(self, count):
        total = 0
        if hasattr(self, "scraper_thread") and self.scraper_thread is not None:
            try:
                total = self.scraper_thread.scraper._total_tracks or 0
            except AttributeError:
                total = 0
        if total > 0:
            self.CounterLabel.setText(f"Songs downloaded {count} of {total}")
        else:
            self.CounterLabel.setText("Songs downloaded " + str(count))

    @pyqtSlot(int)
    def update_song_progress(self, progress):
        self.SongDownloadprogressBar.setValue(progress)
        self.SongDownloadprogress.setValue(progress)

    @pyqtSlot(int)
    def Reset_song_progress(self, progress):
        self.SongDownloadprogressBar.setValue(0)
        self.SongDownloadprogress.setValue(0)

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

    def CloseSongInformation(self):
        self.animation = QPropertyAnimation(self.SONGINFORMATION, b"size")
        self.animation.setDuration(250)
        self.animation.setEndValue(QSize(0, 440))
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.animation.start()

    def OpenSongInformation(self):
        self.animation = QPropertyAnimation(self.SONGINFORMATION, b"size")
        self.animation.setDuration(1000)
        self.animation.setEndValue(QSize(350, 440))
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.animation.start()

    def show_preview(self, state):
        if state == 2:  # 2 corresponds to checked state
            self.preview_window = self.OpenSongInformation()
        else:
            self.CloseSongInformation()

    def exitprogram(self):
        sys.exit()

    def Linkedin(self):
        webbrowser.open("https://www.linkedin.com/in/sunny-patel-30b460204/")


# Main
if __name__ == "__main__":
    # Logging must never stop the app from launching (e.g. a locked-down or
    # read-only log dir). Failure here just means no log file this session.
    with contextlib.suppress(Exception):
        setup_logging()
    # let a terminal ctrl+c terminate cleanly instead of surfacing a traceback
    # on the next qt slot (qt's c++ loop defers python's sigint until then)
    with contextlib.suppress(Exception):
        signal.signal(signal.SIGINT, signal.SIG_DFL)
    # fixed-pixel ui overflows on fractional dpi without this (#64); PassThrough avoids
    # rounding 150%->100%. must precede QApplication. ref: doc.qt.io/qt-5/highdpi.html
    try:
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
    except Exception as exc:  # log so a scaling failure (rendering bugs) is diagnosable
        log.debug("high-dpi setup skipped: %s", exc)
    app = QApplication(sys.argv)
    Screen = MainWindow()
    Screen.setFixedHeight(500)
    Screen.setFixedWidth(750)
    Screen.setWindowFlags(Qt.WindowType.FramelessWindowHint)
    Screen.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    Screen.show()
    sys.exit(app.exec())
