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

__version__ = "2.0.6"

import collections
import concurrent.futures
import os
import sys
import threading
import webbrowser

import requests
from mutagen.easyid3 import EasyID3
from mutagen.id3._frames import APIC
from mutagen.id3 import ID3
from PyQt5.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QRect,
    QSize,
    QUrl,
    Qt,
    QThread,
    pyqtSignal,
    pyqtSlot,
)
from PyQt5.QtMultimedia import QMediaPlayer
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtGui import QColor, QCursor, QFont, QImage, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGraphicsDropShadowEffect,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
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
    detect_spotify_url_type,
    extract_playlist_id,
    sanitize_filename,
)
from Template import Ui_MainWindow


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


def _config_path() -> str:
    return os.path.join(_config_dir(), "config.json")


def _validate_saved_playlists(raw) -> list:
    """Filter and clean saved playlists list."""
    if not isinstance(raw, list):
        return []
    result = []
    for entry in raw:
        if isinstance(entry, dict) and isinstance(entry.get("url"), str) and entry["url"]:
            result.append({
                "url": entry["url"],
                "name": entry.get("name", "") if isinstance(entry.get("name"), str) else "",
                "enabled": entry.get("enabled", True) if isinstance(entry.get("enabled"), bool) else True,
            })
    return result


def load_config() -> dict:
    """Load persisted user config. Missing or corrupt file returns defaults."""
    import json

    defaults = {
        "version": 1,
        "download_path": None,
        "format": "mp3",
        "quality": "192",
        "filename_pattern": "{title} - {artist}",
        "saved_playlists": [],
        "add_meta_tags": True,
        "show_preview": True,
        "playlists_songs_data": {},
    }
    try:
        with open(_config_path(), encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return defaults
        # Load all keys from saved config, with defaults for missing ones
        for key in defaults.keys():
            if key in data:
                defaults[key] = data[key]
        # Also preserve any extra keys from the file (for future compatibility)
        for key, value in data.items():
            if key not in defaults:
                defaults[key] = value
        if defaults["format"] not in SUPPORTED_FORMATS:
            defaults["format"] = "mp3"
        if defaults["quality"] not in SUPPORTED_QUALITIES:
            defaults["quality"] = "192"
        if not isinstance(defaults["filename_pattern"], str) or not defaults["filename_pattern"]:
            defaults["filename_pattern"] = "{title} - {artist}"
        defaults["saved_playlists"] = _validate_saved_playlists(defaults["saved_playlists"])
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
        print(f"[*] Could not save config: {exc}")


def load_saved_playlists(config: dict) -> list[dict]:
    """Extract saved playlists from config."""
    return config.get("saved_playlists", [])


def save_saved_playlists(config: dict, playlists: list[dict]) -> None:
    """Write updated playlists list back into config and persist."""
    config["saved_playlists"] = playlists
    save_config(config)


def format_duration(duration_ms: int | None) -> str:
    """Format duration in milliseconds to MM:SS format."""
    if not duration_ms or duration_ms <= 0:
        return "--:--"
    seconds = duration_ms // 1000
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"


def build_filename(pattern: str, track, track_num: int = 0, ext: str = "mp3") -> str:
    """Build a filename from a pattern and track metadata.

    Tokens: {title}, {artist}, {album}, {year}, {index}, {id}, {ext}
    Missing/None fields become empty strings after substitution.
    Format specs supported: {index:02d} for zero-padded numbers.
    """
    year = (track.release_date or "")[:4] if track.release_date else ""
    mapping = collections.defaultdict(str, {
        "title": track.title or "",
        "artist": track.artists or "",
        "album": track.album or "",
        "year": year,
        "index": track_num,
        "id": track.id or "",
        "ext": ext,
    })
    try:
        result = pattern.format_map(mapping)
    except (ValueError, KeyError):
        result = f"{track.title or 'Unknown'} - {track.artists or 'Unknown'}.{ext}"

    # Only add extension if not already present in pattern
    if not result.endswith(f".{ext}"):
        result = result.strip(" -_.") + f".{ext}"

    result = sanitize_filename(result, allow_spaces=True)
    return result


def get_audio_duration_ms(filepath: str) -> int:
    """Get duration of audio file in milliseconds. Returns 0 if unable to read."""
    try:
        from mutagen.mp3 import MP3
        from mutagen.m4a import M4A
        from mutagen.flac import FLAC

        if not os.path.isfile(filepath):
            return 0

        ext = os.path.splitext(filepath)[1].lower()
        duration_sec = 0

        try:
            if ext == '.mp3':
                audio = MP3(filepath)
                duration_sec = audio.info.length
            elif ext in ['.m4a', '.mp4']:
                audio = M4A(filepath)
                duration_sec = audio.info.length
            elif ext == '.flac':
                audio = FLAC(filepath)
                duration_sec = audio.info.length
            else:
                return 0

            return int(duration_sec * 1000) if duration_sec else 0
        except Exception:
            return 0
    except Exception:
        return 0


# ID3v2.4 Standard Frame IDs (official specification)
ID3_STANDARD_FRAMES = {
    "ID3v1": {
        "TIT2": "Title",
        "TPE1": "Artist",
        "TALB": "Album",
        "TYER": "Year",
        "COMM": "Comment",
        "TCON": "Genre",
    },
    "ID3v2.3": {
        "TIT2": "Title",
        "TIT1": "Content Group Description",
        "TIT3": "Subtitle",
        "TPE1": "Lead Artist/Performer",
        "TPE2": "Band/Orchestra",
        "TPE3": "Conductor",
        "TPE4": "Modified By",
        "TPOS": "Set Number",
        "TRCK": "Track Number",
        "TYER": "Year",
        "TDAT": "Date",
        "TIME": "Time",
        "TALB": "Album",
        "TCON": "Genre",
        "TEXT": "Lyricist",
        "TKEY": "Initial Key",
        "TLAN": "Language",
        "TLEN": "Length",
        "TMED": "Media Type",
        "TMOO": "Mood",
        "TPUB": "Publisher",
        "TRSN": "Radio Station Name",
        "TRSO": "Radio Station Owner",
        "TSSE": "Encoder",
        "TOFN": "Original Filename",
        "TOLE": "Original Lyricist",
        "TOLY": "Original Artist",
        "TOAL": "Original Album",
        "TORY": "Original Year",
        "TSOA": "Album Sort Order",
        "TSOP": "Performer Sort Order",
        "TSOT": "Title Sort Order",
        "TSOW": "Composer Sort Order",
    },
    "ID3v2.4": {
        "TIT2": "Title",
        "TIT1": "Content Group Description",
        "TIT3": "Subtitle",
        "TPE1": "Lead Artist/Performer",
        "TPE2": "Band/Orchestra",
        "TPE3": "Conductor",
        "TPE4": "Modified By",
        "TPOS": "Set Number",
        "TRCK": "Track Number",
        "TDRC": "Recording Date",
        "TDRL": "Release Date",
        "TDTG": "Tagging Date",
        "TALB": "Album",
        "TCON": "Genre",
        "TEXT": "Lyricist",
        "TKEY": "Initial Key",
        "TLAN": "Language",
        "TLEN": "Length",
        "TMED": "Media Type",
        "TMOO": "Mood",
        "TPUB": "Publisher",
        "TRSN": "Radio Station Name",
        "TRSO": "Radio Station Owner",
        "TSSE": "Encoder",
        "TOFN": "Original Filename",
        "TOLE": "Original Lyricist",
        "TOLY": "Original Artist",
        "TOPE": "Original Album",
        "TDOR": "Original Release Date",
        "TSOA": "Album Sort Order",
        "TSOP": "Performer Sort Order",
        "TSOT": "Title Sort Order",
        "TSOW": "Composer Sort Order",
        "TSO2": "Album Artist Sort Order",
        "TSOC": "Composer Sort Order",
        "TCOP": "Copyright",
        "TPRO": "Produced Notice",
        "TDOR": "Original Release Date",
        "APIC": "Picture",
        "TXXX": "User Defined",
    }
}


def normalize_artist_string(artist_str):
    """Normalize artist string: convert non-breaking spaces to regular spaces, clean up."""
    if not artist_str:
        return ""
    # Replace non-breaking space (U+00A0) with regular space
    normalized = artist_str.replace('\u00a0', ' ')
    # Clean up multiple spaces
    normalized = ' '.join(normalized.split())
    return normalized


def get_expected_filename(song, track_num, filename_pattern, audio_format):
    """Calculate expected filename. Single source of truth for all parts of the app."""
    from spotifydown_api import TrackInfo
    # Normalize artist string to handle non-breaking spaces and other issues
    artists = normalize_artist_string(song.get("artists", "Unknown"))
    track_info = TrackInfo(
        id=song.get("spotify_id", ""),
        title=song.get("title", "Unknown"),
        artists=artists,
        album=song.get("album", ""),
        release_date=song.get("release_date", ""),
        cover_url=None,
        duration_ms=None,
        preview_url=song.get("preview_url", ""),
        raw={}
    )
    return build_filename(filename_pattern, track_info, track_num=track_num, ext=audio_format)


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
        filename_pattern: str = "{title} - {artist}",
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
        self.filename_pattern = filename_pattern
        self._counter_lock = threading.Lock()
        self._failed_lock = threading.Lock()
        self._filename_lock = threading.Lock()
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
        if "No video formats" in str(error) or "unavailable" in str(error).lower():
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
        # Use only playlist name, not owner, for consistent folder naming
        return metadata.name.strip(" -")

    def prepare_playlist_folder(self, base_folder, playlist_name):
        if not os.path.exists(base_folder):
            os.makedirs(base_folder)
        # Use the same sanitization as everywhere else for consistency
        safe_name = sanitize_filename(playlist_name, allow_spaces=True)
        if not safe_name:
            safe_name = "Sunnify Playlist"
        playlist_folder = os.path.join(base_folder, safe_name)
        os.makedirs(playlist_folder, exist_ok=True)
        return playlist_folder

    def download_track_audio(self, search_query, destination):
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
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "outtmpl": output_template,
            "ffmpeg_location": ffmpeg_path,
            "retries": 5,
            "socket_timeout": 15,
            "concurrent_fragment_downloads": 4,
            "postprocessors": [postprocessor],
        }
        youtube_url = None
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_query, download=True)
            if info.get("entries"):
                info = info["entries"][0]
            # Capture YouTube URL/ID for tracking
            youtube_url = info.get("webpage_url") or f"https://www.youtube.com/watch?v={info.get('id')}"
            expected_path = base + "." + ext
            if os.path.exists(expected_path):
                return expected_path, youtube_url
            fallback = ydl.prepare_filename(info)
            if os.path.exists(fallback):
                return fallback, youtube_url
        return base + "." + ext, youtube_url

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
        filename = build_filename(self.filename_pattern, track, track_num=track_num, ext=self.audio_format)
        filepath = os.path.join(playlist_folder_path, filename)

        # Filename collision guard: two different tracks can sanitize to the
        # same filename (e.g. "Café" vs "Cafe"). Under parallel downloads the
        # naive os.path.exists check has a TOCTOU race where both workers pass
        # the check and clobber each other's files. Claim the filename via a
        # lock; if taken, suffix with track id to de-dupe.
        with self._filename_lock:
            if filepath in self._in_flight_files:
                base = os.path.splitext(filename)[0]
                filepath = os.path.join(
                    playlist_folder_path,
                    f"{base} [{track.id}].{self.audio_format}",
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
            except SpotifyDownAPIError:
                pass  # Fall through to default_cover_url

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
                self.add_song_meta.emit(song_meta)
                self._finish_track_ui(ok=True)
                return None

            search_query = f"ytsearch1:{track_title} {artists} audio"
            try:
                result = self.download_track_audio(search_query, filepath)
                if isinstance(result, tuple):
                    final_path, youtube_url = result
                else:
                    # Backward compatibility if result is just a path
                    final_path = result
                    youtube_url = None
                # Add YouTube URL to metadata
                song_meta["youtube_url"] = youtube_url or ""
            except Exception as error_status:
                error_msg = self._get_user_friendly_error(error_status, track_title)
                self.error_signal.emit(error_msg)
                print(f"[*] Error downloading '{track_title}': {error_status}")
                with self._failed_lock:
                    self._failed_tracks.append(track_title)
                self._finish_track_ui(ok=False)
                return track_title

            if not final_path or not os.path.exists(final_path):
                self.error_signal.emit(f"'{track_title}' - download failed")
                print(f"[*] Download did not produce an audio file for: {track_title}")
                with self._failed_lock:
                    self._failed_tracks.append(track_title)
                self._finish_track_ui(ok=False)
                return track_title

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

        playlist_id = self.returnSPOT_ID(spotify_playlist_link)
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

        metadata = spotify_api.get_playlist_metadata(playlist_id)
        playlist_display_name = self.format_playlist_name(metadata)
        self.song_Album.emit(playlist_display_name)

        playlist_folder_path = self.prepare_playlist_folder(music_folder, playlist_display_name)

        # Materialize the generator into a list. iter_playlist_tracks is a
        # generator and generators are not thread-safe. Consuming it upfront
        # also lets us pick the right worker count based on track count.
        # Cancel is checked between yields so very large playlists (where
        # iter_playlist_tracks issues hundreds of spclient + per-track embed
        # requests serially) can abort mid-fetch instead of waiting through
        # the full window before the stop button takes effect.
        expected_total = metadata.track_count or 0
        tracks: list = []
        for track in spotify_api.iter_playlist_tracks(playlist_id):
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

        if worker_count == 1:
            for idx, track in enumerate(tracks, start=1):
                if self.is_cancelled():
                    break
                # Reset the per-track progress bar at the top of each iteration
                # so the single-track UI behaves the way it always has.
                self.Resetprogress_signal.emit(0)
                self._download_one_track(
                    track, playlist_folder_path, metadata.cover_url, track_num=idx
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
                            idx,
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
                            # _download_one_track handles errors internally;
                            # this catches unexpected framework-level
                            # exceptions only. Surface them to the UI instead
                            # of silently logging.
                            msg = f"Unexpected worker error: {exc}"
                            print(f"[*] {msg}")
                            self.error_signal.emit(msg)
            finally:
                # Reset parallel_mode only after the executor has fully shut
                # down (context manager exit waits on in-flight workers). If
                # we reset inside the `with`, workers that are still running
                # after a break would observe False and start emitting
                # single-track UI signals.
                self._parallel_mode = False

        if self.is_cancelled():
            self.PlaylistCompleted.emit("Download cancelled")
            return

        # Report completion with failed track count
        if self._failed_tracks:
            self.PlaylistCompleted.emit(f"Done! {len(self._failed_tracks)} track(s) failed")
        else:
            self.PlaylistCompleted.emit("Download Complete!")

    def returnSPOT_ID(self, link):
        """Extract playlist ID from Spotify URL."""
        return extract_playlist_id(link)

    def scrape_track(self, spotify_track_link, music_folder, track_num=1, youtube_url=None):
        """Download a single track from Spotify or use provided YouTube URL."""
        url_type, track_id = detect_spotify_url_type(spotify_track_link)
        if url_type != "track":
            raise ValueError("Expected a track URL")

        try:
            spotify_api = self.ensure_spotifydown_api()
        except SpotifyDownAPIError as exc:
            raise RuntimeError(str(exc)) from exc

        track = spotify_api.get_track(track_id)
        self.song_Album.emit("Single Track Download")

        if not os.path.exists(music_folder):
            os.makedirs(music_folder)

        self.Resetprogress_signal.emit(0)

        track_title = track.title
        artists = track.artists
        filename = build_filename(self.filename_pattern, track, track_num=track_num, ext=self.audio_format)
        filepath = os.path.join(music_folder, filename)

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
            "trackNumber": track_num,
        }

        self.song_meta.emit(dict(song_meta))

        if os.path.exists(filepath):
            self.add_song_meta.emit(song_meta)
            self.increment_counter()
            self.PlaylistCompleted.emit("Track already exists!")
            return (filepath, youtube_url or "")

        # If YouTube URL was provided (e.g. from config), use it directly
        if youtube_url:
            try:
                final_path = self.download_track_audio(youtube_url, filepath)
                if isinstance(final_path, tuple):
                    final_path = final_path[0]
            except Exception as error_status:
                error_msg = self._get_user_friendly_error(error_status, track_title)
                print(f"[*] Error downloading '{track_title}': {error_status}")
                self.PlaylistCompleted.emit(error_msg)
                return (None, "")
        else:
            # Download via YouTube search
            search_query = f"ytsearch1:{track_title} {artists} audio"
            try:
                result = self.download_track_audio(search_query, filepath)
                if isinstance(result, tuple):
                    final_path, youtube_url = result
                else:
                    final_path = result
                    youtube_url = ""
            except Exception as error_status:
                error_msg = self._get_user_friendly_error(error_status, track_title)
                print(f"[*] Error downloading '{track_title}': {error_status}")
                self.PlaylistCompleted.emit(error_msg)
                return (None, "")

        if not final_path or not os.path.exists(final_path):
            print(f"[*] Download did not produce an audio file for: {track_title}")
            self.PlaylistCompleted.emit("Download failed - no audio file produced")
            return (None, "")

        song_meta["file"] = final_path
        # Read and store disk file duration
        disk_duration_ms = get_audio_duration_ms(final_path)
        if disk_duration_ms > 0:
            song_meta["disk_file_duration"] = disk_duration_ms
        self.add_song_meta.emit(song_meta)
        self.increment_counter()
        self.dlprogress_signal.emit(100)
        self.PlaylistCompleted.emit("Download Complete!")
        return (final_path, youtube_url or "")

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
        filename_pattern: str = "{title} - {artist}",
    ):
        super().__init__()
        self.spotify_link = spotify_link
        self.music_folder = music_folder or os.path.join(os.getcwd(), "music")
        self._cancel_event = cancel_event or threading.Event()
        self.scraper = MusicScraper(
            cancel_event=self._cancel_event,
            audio_format=audio_format,
            audio_quality=audio_quality,
            filename_pattern=filename_pattern,
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
            self.progress_update.emit(f"{e}")


class YouTubeFetchThread(QThread):
    """Thread for searching YouTube URLs in background."""
    progress = pyqtSignal(str)
    finished_signal = pyqtSignal(int)

    def __init__(self, songs_data, playlist_id):
        super().__init__()
        self.songs_data = songs_data
        self.playlist_id = playlist_id

    def run(self):
        try:
            from yt_dlp import YoutubeDL
            found_count = 0

            for idx, song in enumerate(self.songs_data):
                if not song.get("youtube_url"):
                    title = song.get("title", "Unknown")
                    artists = song.get("artists", "")
                    search_query = f"{title} {artists} audio"

                    try:
                        ydl_opts = {
                            "quiet": True,
                            "no_warnings": True,
                            "default_search": "ytsearch1",
                            "socket_timeout": 10,
                        }
                        with YoutubeDL(ydl_opts) as ydl:
                            info = ydl.extract_info(search_query, download=False)
                            if info and info.get("entries"):
                                yt_url = info["entries"][0].get("webpage_url")
                                if yt_url:
                                    song["youtube_url"] = yt_url
                                    found_count += 1
                                    self.progress.emit(f"Found {found_count}/{len(self.songs_data)}")
                    except Exception as e:
                        self.progress.emit(f"Searching... {idx + 1}/{len(self.songs_data)}")

            self.finished_signal.emit(found_count)
        except Exception as e:
            self.progress.emit(f"Error: {str(e)[:50]}")


class RedownloadThread(QThread):
    """Thread for re-downloading a single track."""
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, track_id, track_url, playlist_folder, audio_format, audio_quality, filename_pattern):
        super().__init__()
        self.track_id = track_id
        self.track_url = track_url
        self.playlist_folder = playlist_folder
        self.audio_format = audio_format
        self.audio_quality = audio_quality
        self.filename_pattern = filename_pattern

    def run(self):
        try:
            cancel_event = threading.Event()
            scraper = MusicScraper(
                cancel_event=cancel_event,
                audio_format=self.audio_format,
                audio_quality=self.audio_quality,
                filename_pattern=self.filename_pattern,
            )
            scraper.scrape_track(self.track_url, self.playlist_folder)
            self.finished_signal.emit("✓ Track re-downloaded")
        except Exception as e:
            self.error_signal.emit(f"Error: {str(e)[:50]}")


class SyncAllThread(QThread):
    """Thread to sequentially sync multiple playlists."""
    sync_progress = pyqtSignal(str)
    sync_progress_count = pyqtSignal(int, int)  # (current, total) for progress bar
    sync_done = pyqtSignal(str)
    playlist_started = pyqtSignal(str, int)
    song_meta_for_tags = pyqtSignal(dict)  # Forward metadata to MainWindow for tagging

    def __init__(
        self,
        playlists: list[dict],
        music_folder: str,
        cancel_event: threading.Event,
        *,
        audio_format: str = "mp3",
        audio_quality: str = "192",
        filename_pattern: str = "{title} - {artist}",
        config: dict | None = None,
    ):
        super().__init__()
        self.playlists = playlists
        self.music_folder = music_folder
        self._cancel_event = cancel_event
        self.audio_format = audio_format
        self.audio_quality = audio_quality
        self.filename_pattern = filename_pattern
        self.config = config or {}
        self._current_scraper: MusicScraper | None = None
        self._current_count = 0
        self._total_count = 0

    def _on_track_added(self, meta):
        """Slot: called when a track is added/downloaded."""
        self._current_count += 1
        self.sync_progress_count.emit(self._current_count, self._total_count)
        # Forward metadata to MainWindow for tag writing
        self.song_meta_for_tags.emit(meta)

    def _estimate_playlist_size(self, url: str) -> int:
        """Estimate total tracks in playlist by fetching metadata."""
        try:
            pid = extract_playlist_id(url)
            client = PlaylistClient()
            meta = client.get_playlist_metadata(pid)
            return meta.track_count if meta else 0
        except Exception:
            return 0

    def request_cancel(self):
        """Request cancellation."""
        self._cancel_event.set()

    def run(self):
        """Iterate playlists sequentially, downloading missing tracks from each."""
        total = len(self.playlists)
        cancelled = False
        for idx, entry in enumerate(self.playlists, start=1):
            if self._cancel_event.is_set():
                cancelled = True
                break
            url = entry.get("url", "")
            name = entry.get("name") or url
            self.playlist_started.emit(name, idx)
            self.sync_progress.emit(f"Syncing {idx}/{total}: {name}")

            scraper = MusicScraper(
                cancel_event=self._cancel_event,
                audio_format=self.audio_format,
                audio_quality=self.audio_quality,
                filename_pattern=self.filename_pattern,
            )
            self._current_scraper = scraper
            self._current_count = 0

            # Connect to track completion for progress tracking
            scraper.add_song_meta.connect(self._on_track_added, Qt.QueuedConnection)
            scraper.PlaylistCompleted.connect(
                lambda msg, n=name: self.sync_progress.emit(f"{n}: {msg}"),
                Qt.QueuedConnection
            )
            scraper.error_signal.connect(
                self.sync_progress.emit,
                Qt.QueuedConnection
            )

            try:
                # Use config.json as source of truth for tracks
                pid = extract_playlist_id(url)
                songs_data = self.config.get("playlists_songs_data", {}).get(pid, [])

                if songs_data:
                    # Use songs from config.json (user's source of truth)
                    # Build the correct playlist folder path
                    from spotifydown_api import sanitize_filename
                    safe_name = sanitize_filename(name, allow_spaces=True)
                    playlist_folder = os.path.join(self.music_folder, safe_name)

                    self._total_count = len(songs_data)
                    self._current_count = 0
                    self.sync_progress_count.emit(0, self._total_count)
                    self.sync_progress.emit(f"Syncing {self._total_count} tracks from {name}...")

                    # Download tracks from config.json list
                    for track_idx, song in enumerate(songs_data):
                        if self._cancel_event.is_set():
                            break
                        self._current_count = track_idx + 1
                        self.sync_progress_count.emit(self._current_count, self._total_count)

                        try:
                            track_url = song.get("track_url", "")
                            # If no track_url, try to construct it from spotify_id
                            if not track_url:
                                spotify_id = song.get("spotify_id", "")
                                if spotify_id:
                                    track_url = f"https://open.spotify.com/track/{spotify_id}"

                            if not track_url:
                                continue

                            # Check if file already exists before downloading
                            filename = get_expected_filename(song, track_idx + 1, self.filename_pattern, self.audio_format)
                            filepath = os.path.join(playlist_folder, filename)

                            if os.path.exists(filepath):
                                self.sync_progress.emit(f"Skipped: {song.get('title', 'Unknown')} (already exists)")
                                continue

                            # Download the track (pass track_num and youtube_url from config)
                            yt_url = song.get("youtube_url", "")
                            result = scraper.scrape_track(track_url, playlist_folder, track_num=track_idx + 1, youtube_url=yt_url)
                            if result:
                                filepath, yt_url = result
                                if filepath:
                                    self.sync_progress.emit(f"Downloaded: {song.get('title', 'Unknown')}")

                                    # Update song data in config with youtube_url and disk duration
                                    if yt_url:
                                        song["youtube_url"] = yt_url
                                    disk_duration = get_audio_duration_ms(filepath)
                                    if disk_duration > 0:
                                        song["disk_file_duration"] = disk_duration
                                    self.config["playlists_songs_data"][pid] = songs_data
                                    # Persist to disk
                                    save_config(self.config)

                                    # Emit metadata for tagging
                                    meta = {
                                        "file": filepath,
                                        "title": song.get("title", ""),
                                        "artists": song.get("artists", ""),
                                        "album": song.get("album", ""),
                                        "releaseDate": song.get("release_date", ""),
                                        "spotifyId": song.get("spotify_id", ""),
                                        "trackNumber": track_idx + 1,
                                        "youtubeUrl": yt_url or song.get("youtube_url", ""),
                                        "previewUrl": song.get("preview_url", ""),
                                    }
                                    self.song_meta_for_tags.emit(meta)
                        except Exception as e:
                            self.sync_progress.emit(f"Error downloading {song.get('title')}: {str(e)[:50]}")
                else:
                    # Fallback: fetch from Spotify if no config data
                    self._total_count = self._estimate_playlist_size(url)
                    self._current_count = 0
                    self.sync_progress_count.emit(0, self._total_count)
                    self.sync_progress.emit(f"Fetching {self._total_count} tracks from {name}...")
                    scraper.scrape_playlist(url, self.music_folder)
            except Exception as exc:
                self.sync_progress.emit(f"Error syncing {name}: {exc}")
            finally:
                self._current_count = 0
                self._total_count = 0

        self._current_scraper = None
        if cancelled:
            self.sync_done.emit("Sync cancelled")
        else:
            self.sync_done.emit(f"Sync complete — {total} playlist(s) checked")


def _fetch_cover_bytes(url: str) -> bytes | None:
    """Download cover image bytes, returning None on any failure."""
    if not url:
        return None
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200 and resp.content:
            return resp.content
    except (requests.RequestException, OSError) as exc:
        print(f"[*] Error fetching cover: {exc}")
    return None


def read_id3_tags(filename: str) -> dict:
    """Read ALL ID3 tags from an MP3 file. Returns dict: {frame_id: value}"""
    try:
        from mutagen.id3 import ID3
        id3 = ID3(filename)
    except Exception:
        return {}

    tags_dict = {}

    # Read ALL frames from the ID3 tag
    for frame_id, frame in id3.items():
        if frame_id == "APIC":
            # Handle picture frames
            tags_dict[frame_id] = f"[Image: {frame.mime}]"
        elif hasattr(frame, "text") and frame.text:
            # Text frames
            tags_dict[frame_id] = str(frame.text[0])
        elif frame_id.startswith("TXXX"):
            # Custom text frames
            desc = getattr(frame, "desc", "Unknown")
            text = str(frame.text[0]) if hasattr(frame, "text") and frame.text else ""
            tags_dict[frame_id] = text
        else:
            tags_dict[frame_id] = str(frame)

    return tags_dict


def _write_metadata_mp3(filename: str, tags: dict, cover_bytes: bytes | None) -> None:
    """Write ID3 tags + embedded cover art to an MP3. Preserves existing tags."""
    # Read existing ID3 tags if they exist
    try:
        audio = EasyID3(filename)
    except Exception:
        audio = EasyID3()

    # Update with new values (preserve existing ones not in tags dict)
    audio["title"] = tags.get("title", audio.get("title", [""])[0])
    audio["artist"] = tags.get("artists", audio.get("artist", [""])[0])
    audio["album"] = tags.get("album", audio.get("album", [""])[0])
    audio["date"] = tags.get("releaseDate", audio.get("date", [""])[0])
    # Save label in TPUB (Publisher) field
    label = tags.get("label", audio.get("publisher", [""])[0] if audio.get("publisher") else "")
    if label:
        audio["publisher"] = label
    track_num = tags.get("trackNumber") or 0
    if track_num:
        audio["tracknumber"] = str(track_num)
    audio.save()

    # Write additional frames using ID3 directly
    try:
        id3 = ID3(filename)
    except Exception:
        # If ID3 tag doesn't exist, create a new one
        id3 = ID3()

    # Update cover art if provided
    if cover_bytes:
        id3["APIC"] = APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=cover_bytes)

    # Save YouTube URL as a custom frame
    youtube_url = tags.get("youtube_url", "")
    if youtube_url:
        from mutagen.id3._frames import TXXX
        id3["TXXX:YouTubeURL"] = TXXX(encoding=3, desc="YouTubeURL", text=[youtube_url])

    id3.save(filename, v2_version=4)


def _write_metadata_m4a(filename: str, tags: dict, cover_bytes: bytes | None) -> None:
    """Write iTunes atom tags + embedded cover art to an M4A/MP4."""
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
    youtube_url = tags.get("youtube_url", "")
    if youtube_url:
        audio["----:com.apple.itunes:YouTubeURL"] = [youtube_url.encode("utf-8")]
    if cover_bytes:
        audio["covr"] = [MP4Cover(cover_bytes, imageformat=MP4Cover.FORMAT_JPEG)]
    audio.save()


def _write_metadata_flac(filename: str, tags: dict, cover_bytes: bytes | None) -> None:
    """Write Vorbis comments + embedded cover art to a FLAC."""
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
    youtube_url = tags.get("youtube_url", "")
    if youtube_url:
        audio["YouTubeURL"] = youtube_url
    if cover_bytes:
        pic = Picture()
        pic.type = 3  # Front cover
        pic.mime = "image/jpeg"
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
            print("[*] FileName : ", self.filename)
            ext = os.path.splitext(self.filename)[1].lower()
            writer = _METADATA_WRITERS.get(ext)
            if writer is None:
                self.tags_success.emit("Tags skipped (unsupported container)")
                return

            cover_bytes = _fetch_cover_bytes(self.tags.get("cover", ""))
            writer(self.filename, self.tags, cover_bytes)
            self.tags_success.emit("Tags added successfully")
        except Exception as e:
            print(f"[*] Error writing meta tags: {e}")


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
        except Exception:
            pass  # Silently fail for thumbnails

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
        # Min width + resizable so the full path fits on any screen; wider
        # default because macOS path strings are long (`/Users/.../Music/...`).
        self.setMinimumWidth(560)
        self.resize(620, self.sizeHint().height())
        self._config = dict(config)

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

        self._pattern_input = QLineEdit(self._config.get("filename_pattern", "{title} - {artist}"))
        self._pattern_input.setPlaceholderText("{title} - {artist}")
        self._pattern_input.textChanged.connect(self._validate_pattern)
        self._pattern_help_btn = QPushButton("?")
        self._pattern_help_btn.setMaximumWidth(24)
        self._pattern_help_btn.clicked.connect(self._show_pattern_help)
        self._pattern_warn = QLabel("")
        self._pattern_warn.setStyleSheet("color: red; font-size: 9px;")

        pattern_row = QHBoxLayout()
        pattern_row.addWidget(self._pattern_input, 1)
        pattern_row.addWidget(self._pattern_help_btn)

        # Metadata path display
        from Spotify_Downloader import _config_path
        metadata_path = _config_path()
        self._metadata_label = QLineEdit(metadata_path)
        self._metadata_label.setReadOnly(True)
        self._metadata_label.setFrame(False)
        self._metadata_label.setCursorPosition(0)
        self._metadata_label.setToolTip(metadata_path)
        self._metadata_label.setStyleSheet("QLineEdit { background: transparent; padding: 0; }")
        reveal_btn = QPushButton("Reveal in Finder")
        reveal_btn.clicked.connect(self._reveal_metadata_folder)

        metadata_row = QHBoxLayout()
        metadata_row.addWidget(self._metadata_label, 1)
        metadata_row.addWidget(reveal_btn)

        form = QFormLayout()
        form.addRow("Download folder:", folder_row)
        form.addRow("Audio format:", self._format_cb)
        form.addRow("Audio quality:", self._quality_cb)
        form.addRow("Filename pattern:", pattern_row)
        form.addRow("", self._pattern_warn)
        form.addRow("Metadata files:", metadata_row)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(btns)

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
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
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

    def _show_pattern_help(self):
        """Show help dialog for pattern tokens."""
        QMessageBox.information(
            self, "Filename Pattern Tokens",
            "Available tokens:\n"
            "  {index:02d}  — track number with zero-padding (01, 02, ...)\n"
            "  {title}     — track title\n"
            "  {artist}    — artist name(s)\n"
            "  {album}     — album name\n"
            "  {year}      — release year (4 digits)\n"
            "  {id}        — Spotify track ID\n"
            "  {ext}       — file extension (mp3, m4a, flac, etc.)\n\n"
            "Examples:\n"
            "  {index:02d}. {title}\n"
            "  {index:02d} {artist} - {title}\n"
            "  {artist}/{album}/{index:02d} {title}.{ext}\n\n"
            "Default: {title} - {artist}"
        )

    def _validate_pattern(self, text: str):
        """Validate filename pattern by attempting build_filename."""
        pattern = text.strip() or "{title} - {artist}"
        try:
            from spotifydown_api import TrackInfo
            dummy = TrackInfo(
                id="abc123", title="Test Song", artists="Test Artist",
                album="Album", release_date="2024-01-01",
                cover_url=None, duration_ms=None, preview_url=None, raw={}
            )
            result = build_filename(pattern, dummy, track_num=1, ext="mp3")
            if result in (".mp3", "Unknown.mp3"):
                self._pattern_warn.setText("Pattern produces empty filename — default will be used")
            else:
                self._pattern_warn.setText("")
        except Exception:
            self._pattern_warn.setText("Invalid pattern — default will be used")

    def _reveal_metadata_folder(self):
        """Open metadata folder in Finder (for SettingsDialog)."""
        self._reveal_metadata_folder_impl()

    def _reveal_metadata_folder_main(self):
        """Open metadata folder in Finder (for MainWindow settings panel)."""
        self._reveal_metadata_folder_impl()

    def _reveal_metadata_folder_impl(self):
        """Implementation of metadata folder reveal."""
        try:
            from Spotify_Downloader import _config_path
            import subprocess
            import sys

            config_path = _config_path()
            config_dir = os.path.dirname(config_path)

            if not os.path.isdir(config_dir):
                os.makedirs(config_dir, exist_ok=True)

            if sys.platform == "darwin":
                subprocess.Popen(["open", config_dir])
            elif sys.platform == "win32":
                subprocess.Popen(f"explorer {config_dir}")
            else:
                subprocess.Popen(["xdg-open", config_dir])

            self.statusMsg.setText("Opening metadata folder...")
        except Exception as e:
            self.statusMsg.setText(f"Error: {str(e)[:40]}")

    def result_config(self) -> dict:
        self._config["download_path"] = self._folder_label.text()
        self._config["format"] = self._format_cb.currentText()
        self._config["quality"] = self._quality_cb.currentText().split()[0]
        pattern = self._pattern_input.text().strip() or "{title} - {artist}"
        self._config["filename_pattern"] = pattern
        return self._config


# Main Window
class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        """MainWindow constructor"""
        super().__init__()
        self.setupUi(self)

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

        # Load preference defaults
        self.showPreviewCheck.setChecked(self._config.get("show_preview", True))
        self.showPreviewCheck.stateChanged.connect(self.show_preview)
        self.showPreviewCheck.stateChanged.connect(self._save_preview_pref)

        self.Closed.clicked.connect(self.exitprogram)
        self.Select_Home.clicked.connect(self.Linkedin)
        self.SettingsBtn.clicked.connect(self.open_settings)

        # Hide the Album row in the preview panel: Spotify's unauthenticated
        # embed endpoints do not expose album name anywhere we can reach it,
        # so the field would always be blank. A missing row reads better than
        # a permanently empty label.
        self.label_8.hide()
        self.AlbumText.hide()

        # Initialize content panels and sidebar
        self._sync_thread = None
        self._current_view = "home"  # Track which view is active
        self._setup_sidebar()
        self._setup_content_panels()
        # Hide old UI at startup, show home view
        if hasattr(self, 'frame'):
            self.frame.hide()
        if hasattr(self, 'SONGINFORMATION'):
            self.SONGINFORMATION.hide()

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
        except OSError:
            return False

    def _prompt_download_location(self):
        """Prompt user to select download location. Returns True if selected."""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Download Folder",
            os.path.expanduser("~"),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
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
        if dialog.exec_() == QDialog.Accepted:
            new = dialog.result_config()
            if new.get("download_path"):
                self.download_path = new["download_path"]
                self._download_path_set = True
            self._config.update(
                {
                    "download_path": self.download_path,
                    "format": new.get("format", "mp3"),
                    "quality": new.get("quality", "192"),
                }
            )
            save_config(self._config)
            self.statusMsg.setText("Settings saved")

    def _setup_sidebar(self):
        """Create the left navigation sidebar with buttons and playlist list."""
        self._sidebar = QFrame(self.centralwidget)
        self._sidebar.setGeometry(QRect(0, 0, 280, 600))
        self._sidebar.setObjectName("SIDEBAR")
        self._sidebar.setStyleSheet(
            "QFrame#SIDEBAR { background-color: qlineargradient(spread:pad, x1:0, y1:0, "
            "x2:1, y2:0, stop:0 rgba(80, 80, 80, 240), stop:1 rgba(60, 60, 60, 240)); "
            "border-right: 1px solid rgba(0,0,0,100); }"
        )

        # Navigation buttons
        self._nav_add_btn = QPushButton("➕ Add Playlist", self._sidebar)
        self._nav_add_btn.setGeometry(QRect(10, 10, 260, 32))
        self._nav_add_btn.setStyleSheet("QPushButton { font-size: 11px; font-weight: bold; background: rgba(100,150,255,100); border: 1px solid #666; border-radius: 4px; color: white; }")
        self._nav_add_btn.clicked.connect(lambda: self._show_view("add_playlist"))

        self._nav_settings_btn = QPushButton("⚙️ Settings", self._sidebar)
        self._nav_settings_btn.setGeometry(QRect(10, 50, 260, 32))
        self._nav_settings_btn.setStyleSheet("QPushButton { font-size: 11px; font-weight: bold; background: rgba(100,150,255,100); border: 1px solid #666; border-radius: 4px; color: white; }")
        self._nav_settings_btn.clicked.connect(lambda: self._show_view("settings"))

        # Playlists section
        pl_title = QLabel("📋 Playlists", self._sidebar)
        pl_title.setGeometry(QRect(10, 90, 260, 16))
        pl_title.setAlignment(Qt.AlignCenter)
        pl_title.setStyleSheet("color: white; font-weight: bold; font-size: 11px;")

        self._pl_list = QListWidget(self._sidebar)
        self._pl_list.setGeometry(QRect(10, 110, 260, 210))
        self._pl_list.setUniformItemSizes(False)
        self._pl_list.setStyleSheet(
            "QListWidget { background: rgba(255,255,255,70); border-radius: 4px; color: black; "
            "font-size: 9px; } QListWidget::item:selected { background: rgba(100,150,255,100); } "
            "QListWidget::item { padding: 3px; }"
        )
        self._pl_list.itemChanged.connect(self._on_playlist_item_changed)
        self._pl_list.itemSelectionChanged.connect(self._on_playlist_selection_changed)

        # Control buttons
        self._pl_remove_btn = QPushButton("✕ Remove", self._sidebar)
        self._pl_remove_btn.setGeometry(QRect(10, 330, 80, 24))
        self._pl_remove_btn.setStyleSheet("QPushButton { font-size: 9px; }")
        self._pl_remove_btn.clicked.connect(self._playlist_remove)

        self._pl_sync_btn = QPushButton("⬇ Sync All", self._sidebar)
        self._pl_sync_btn.setGeometry(QRect(100, 330, 170, 24))
        self._pl_sync_btn.setStyleSheet("QPushButton { font-size: 9px; }")
        self._pl_sync_btn.clicked.connect(self._playlist_sync_all)

        # Progress tracking
        self._sync_progress_bar = QProgressBar(self._sidebar)
        self._sync_progress_bar.setGeometry(QRect(10, 390, 260, 12))
        self._sync_progress_bar.setStyleSheet(
            "QProgressBar { background: rgba(0,0,0,100); border: 1px solid #666; border-radius: 3px; } "
            "QProgressBar::chunk { background: #4CAF50; }"
        )
        self._sync_progress_bar.setVisible(False)

        self._sync_phase_label = QLabel("", self._sidebar)
        self._sync_phase_label.setGeometry(QRect(10, 405, 260, 85))
        self._sync_phase_label.setWordWrap(True)
        self._sync_phase_label.setAlignment(Qt.AlignTop | Qt.AlignCenter)
        self._sync_phase_label.setStyleSheet("color: #aaa; font-size: 8px;")

        self._refresh_playlist_list()
        self._shift_main_content_for_sidebar()

    def _setup_content_panels(self):
        """Create separate content panels for different views."""
        # Add Playlist panel
        self._add_playlist_panel = QFrame(self.centralwidget)
        self._add_playlist_panel.setGeometry(QRect(280, 0, 1170, 600))
        self._add_playlist_panel.setStyleSheet(
            "QFrame { background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, "
            "stop:0 rgba(40, 40, 40, 255), stop:1 rgba(30, 30, 30, 255)); }"
        )
        self._add_playlist_panel.hide()

        pl_label = QLabel("Add Playlist URL", self._add_playlist_panel)
        pl_label.setGeometry(QRect(40, 50, 300, 25))
        pl_label.setStyleSheet("color: white; font-weight: bold; font-size: 14px;")

        self._add_pl_input = QLineEdit(self._add_playlist_panel)
        self._add_pl_input.setGeometry(QRect(40, 85, 800, 35))
        self._add_pl_input.setPlaceholderText("https://open.spotify.com/playlist/...")
        self._add_pl_input.setStyleSheet("QLineEdit { padding: 8px; border-radius: 4px; font-size: 11px; background: white; color: black; border: 1px solid #999; }")

        self._add_pl_btn = QPushButton("Add Playlist", self._add_playlist_panel)
        self._add_pl_btn.setGeometry(QRect(860, 85, 140, 35))
        self._add_pl_btn.setStyleSheet("QPushButton { background: rgba(100,150,255,180); border: 1px solid #666; border-radius: 4px; color: white; font-weight: bold; }")
        self._add_pl_btn.clicked.connect(self._add_new_playlist)

        # Settings panel
        self._settings_panel = QFrame(self.centralwidget)
        self._settings_panel.setGeometry(QRect(280, 0, 1170, 600))
        self._settings_panel.setStyleSheet(
            "QFrame { background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, "
            "stop:0 rgba(40, 40, 40, 255), stop:1 rgba(30, 30, 30, 255)); }"
        )
        self._settings_panel.hide()

        settings_label = QLabel("Filename Pattern", self._settings_panel)
        settings_label.setGeometry(QRect(40, 50, 300, 25))
        settings_label.setStyleSheet("color: white; font-weight: bold; font-size: 14px;")

        self._pattern_field = QLineEdit(self._settings_panel)
        self._pattern_field.setGeometry(QRect(40, 85, 800, 35))
        self._pattern_field.setText(self._config.get("filename_pattern", "{title} - {artist}"))
        self._pattern_field.setPlaceholderText("{title} - {artist}")
        self._pattern_field.setStyleSheet("QLineEdit { padding: 8px; border-radius: 4px; font-size: 11px; background: white; color: black; border: 1px solid #999; }")
        self._pattern_field.editingFinished.connect(self._on_pattern_changed)

        pattern_help = QPushButton("?", self._settings_panel)
        pattern_help.setGeometry(QRect(860, 85, 50, 35))
        pattern_help.setStyleSheet("QPushButton { background: rgba(100,150,255,180); border: 1px solid #666; border-radius: 4px; color: white; font-weight: bold; }")
        pattern_help.clicked.connect(self._show_pattern_help)

        # Add meta tags checkbox
        from PyQt5.QtWidgets import QCheckBox

        meta_label = QLabel("Add Meta Tags", self._settings_panel)
        meta_label.setGeometry(QRect(40, 140, 200, 20))
        meta_label.setStyleSheet("color: white; font-size: 12px;")

        self._settings_meta_check = QCheckBox(self._settings_panel)
        self._settings_meta_check.setGeometry(QRect(40, 165, 20, 20))
        self._settings_meta_check.setChecked(self._config.get("add_meta_tags", True))
        self._settings_meta_check.stateChanged.connect(self._save_meta_tags_pref)
        self._settings_meta_check.setStyleSheet("QCheckBox { color: white; }")

        # Metadata files path
        metadata_label = QLabel("Metadata Files", self._settings_panel)
        metadata_label.setGeometry(QRect(40, 210, 200, 20))
        metadata_label.setStyleSheet("color: white; font-size: 12px;")

        from Spotify_Downloader import _config_path
        metadata_path = _config_path()
        metadata_path_display = QLineEdit(metadata_path, self._settings_panel)
        metadata_path_display.setGeometry(QRect(40, 235, 850, 35))
        metadata_path_display.setReadOnly(True)
        metadata_path_display.setStyleSheet("QLineEdit { padding: 8px; border-radius: 4px; font-size: 10px; background: rgba(255,255,255,20); color: #aaa; border: 1px solid #666; }")

        reveal_metadata_btn = QPushButton("Reveal in Finder", self._settings_panel)
        reveal_metadata_btn.setGeometry(QRect(500, 235, 160, 35))
        reveal_metadata_btn.setStyleSheet("QPushButton { background: rgba(100,150,255,180); border: 1px solid #666; border-radius: 4px; color: white; font-weight: bold; font-size: 10px; }")
        reveal_metadata_btn.clicked.connect(self._reveal_metadata_folder_main)

        # Home panel (welcome screen)
        self._home_panel = QFrame(self.centralwidget)
        self._home_panel.setGeometry(QRect(280, 0, 770, 500))
        self._home_panel.setStyleSheet(
            "QFrame { background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, "
            "stop:0 rgba(40, 40, 40, 255), stop:1 rgba(30, 30, 30, 255)); }"
        )
        self._home_panel.show()

        welcome_title = QLabel("Sunnify", self._home_panel)
        welcome_title.setGeometry(QRect(40, 80, 400, 40))
        welcome_title.setStyleSheet("color: white; font-weight: bold; font-size: 32px;")

        welcome_subtitle = QLabel("Spotify Downloader", self._home_panel)
        welcome_subtitle.setGeometry(QRect(40, 125, 400, 25))
        welcome_subtitle.setStyleSheet("color: #aaa; font-size: 14px;")

        welcome_text = QLabel(
            "Get started:\n"
            "• Click \"➕ Add Playlist\" to add playlists\n"
            "• Click \"⚙️ Settings\" to configure options\n"
            "• Use \"⬇ Sync All\" to download all playlists\n\n"
            "Select a playlist from the list and press Download\n"
            "to start downloading individual playlists.",
            self._home_panel
        )
        welcome_text.setGeometry(QRect(40, 170, 500, 150))
        welcome_text.setStyleSheet("color: #ccc; font-size: 12px; line-height: 1.6;")
        welcome_text.setWordWrap(True)

        # Fix Songs panel
        self._fix_songs_panel = QFrame(self.centralwidget)
        self._fix_songs_panel.setGeometry(QRect(280, 0, 1170, 600))
        self._fix_songs_panel.setStyleSheet(
            "QFrame { background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, "
            "stop:0 rgba(40, 40, 40, 255), stop:1 rgba(30, 30, 30, 255)); }"
        )
        self._fix_songs_panel.hide()

        fix_label = QLabel("Song Track Links", self._fix_songs_panel)
        fix_label.setGeometry(QRect(40, 20, 300, 25))
        fix_label.setStyleSheet("color: white; font-weight: bold; font-size: 14px;")

        self._fix_playlist_label = QLabel("No playlist selected", self._fix_songs_panel)
        self._fix_playlist_label.setGeometry(QRect(40, 45, 900, 20))
        self._fix_playlist_label.setStyleSheet("color: #4CAF50; font-size: 12px; font-weight: bold;")

        info_text = QLabel("Select a playlist in the sidebar to view and manage its track links", self._fix_songs_panel)
        info_text.setGeometry(QRect(40, 70, 900, 25))
        info_text.setStyleSheet("color: #aaa; font-size: 10px;")
        info_text.setWordWrap(True)

        self._songs_table = QTableWidget(self._fix_songs_panel)
        self._songs_table.setGeometry(QRect(40, 105, 1080, 360))
        self._songs_table.setColumnCount(4)
        self._songs_table.setHorizontalHeaderLabels(["Song", "🎵 Spotify", "🎬 YouTube", "💾 Disk"])
        self._songs_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self._songs_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self._songs_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self._songs_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self._songs_table.setColumnWidth(0, 200)
        self._songs_table.setColumnWidth(1, 140)
        self._songs_table.setColumnWidth(2, 180)
        self._songs_table.setColumnWidth(3, 380)
        self._songs_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._songs_table.setStyleSheet(
            "QTableWidget { background: rgba(255,255,255,50); border-radius: 4px; color: white; "
            "gridline-color: rgba(255,255,255,20); font-size: 9px; } "
            "QHeaderView::section { background: rgba(0,0,0,100); color: white; padding: 4px; } "
            "QTableWidget::item { padding: 4px; }"
        )

        fetch_spotify_btn = QPushButton("📥 Fetch from Spotify", self._fix_songs_panel)
        fetch_spotify_btn.setGeometry(QRect(40, 475, 180, 32))
        fetch_spotify_btn.setStyleSheet("QPushButton { background: #1DB954; border: 1px solid #666; border-radius: 4px; color: white; font-weight: bold; }")
        fetch_spotify_btn.clicked.connect(self._fetch_from_spotify)

        fetch_youtube_btn = QPushButton("🔍 Find YouTube URLs", self._fix_songs_panel)
        fetch_youtube_btn.setGeometry(QRect(240, 475, 180, 32))
        fetch_youtube_btn.setStyleSheet("QPushButton { background: #FF0000; border: 1px solid #666; border-radius: 4px; color: white; font-weight: bold; }")
        fetch_youtube_btn.clicked.connect(self._fetch_youtube_urls)

        scan_disk_btn = QPushButton("💾 Scan disk", self._fix_songs_panel)
        scan_disk_btn.setGeometry(QRect(440, 475, 140, 32))
        scan_disk_btn.setStyleSheet("QPushButton { background: #2196F3; border: 1px solid #666; border-radius: 4px; color: white; font-weight: bold; }")
        scan_disk_btn.clicked.connect(self._scan_disk_state)

        self._sync_playlist_btn = QPushButton("⬇ Sync", self._fix_songs_panel)
        self._sync_playlist_btn.setGeometry(QRect(600, 475, 120, 32))
        self._sync_playlist_btn.setStyleSheet("QPushButton { background: #4CAF50; border: 1px solid #666; border-radius: 4px; color: white; font-weight: bold; }")
        self._sync_playlist_btn.clicked.connect(self._sync_single_playlist)

        # Style main download view frame to match new panels
        if hasattr(self, 'frame'):
            self.frame.setStyleSheet(
                "QFrame { background: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:1, "
                "stop:0 rgba(40, 40, 40, 255), stop:1 rgba(30, 30, 30, 255)); }"
            )

    def _save_preview_pref(self, state):
        """Save preview preference to config."""
        self._config["show_preview"] = self.showPreviewCheck.isChecked()
        save_config(self._config)

    def _save_meta_tags_pref(self, state):
        """Save meta tags preference to config."""
        if hasattr(self, '_settings_meta_check'):
            self._config["add_meta_tags"] = self._settings_meta_check.isChecked()
        elif hasattr(self, 'addMetaTagsCheck'):
            self._config["add_meta_tags"] = self.addMetaTagsCheck.isChecked()
        save_config(self._config)

    def _show_pattern_help(self):
        """Show help dialog for pattern tokens."""
        QMessageBox.information(
            self, "Filename Pattern Tokens",
            "Available tokens:\n"
            "  {index:02d}  — track number with zero-padding (01, 02, ...)\n"
            "  {title}     — track title\n"
            "  {artist}    — artist name(s)\n"
            "  {album}     — album name\n"
            "  {year}      — release year (4 digits)\n"
            "  {id}        — Spotify track ID\n"
            "  {ext}       — file extension (mp3, m4a, flac, etc.)\n\n"
            "Examples:\n"
            "  {index:02d}. {title}\n"
            "  {index:02d} {artist} - {title}\n"
            "  {artist}/{album}/{index:02d} {title}.{ext}\n\n"
            "Default: {title} - {artist}"
        )

    def _fetch_playlist_name_async(self, entry):
        """Fetch playlist name from Spotify in background thread."""
        def fetch():
            try:
                pid = extract_playlist_id(entry["url"])
                client = PlaylistClient()
                meta = client.get_playlist_metadata(pid)
                if meta and meta.name:
                    # Update config with fetched name
                    playlists = load_saved_playlists(self._config)
                    for p in playlists:
                        if p["url"] == entry["url"]:
                            p["name"] = meta.name
                    save_saved_playlists(self._config, playlists)
                    # Refresh UI on main thread
                    self._refresh_playlist_list()
            except Exception:
                pass

        t = threading.Thread(target=fetch, daemon=True)
        t.start()

    def _on_pattern_changed(self):
        """Handle filename pattern changes in sidebar."""
        pattern = self._pattern_field.text().strip() or "{title} - {artist}"
        self._config["filename_pattern"] = pattern
        save_config(self._config)
        # Refresh songs list since file detection depends on the pattern
        if hasattr(self, '_current_view') and self._current_view == "fix_songs":
            self._refresh_songs_list()

    def _on_playlist_item_changed(self, item):
        """Handle checkbox state changes for playlist items."""
        url = item.data(Qt.UserRole)
        is_checked = item.checkState() == Qt.Checked

        # Update config
        playlists = load_saved_playlists(self._config)
        for p in playlists:
            if p["url"] == url:
                p["enabled"] = is_checked
        save_saved_playlists(self._config, playlists)

        # Refresh playlist list to show updated check state
        self._refresh_playlist_list()

        # If we're viewing songs, refresh the list when playlist selection changes
        if hasattr(self, '_current_view') and self._current_view == "fix_songs":
            self._refresh_songs_list()

    def _on_playlist_selection_changed(self):
        """Handle when user selects a different playlist in the sidebar."""
        # Always show Fix Songs view when a playlist is selected
        if hasattr(self, '_fix_songs_panel'):
            self._show_view("fix_songs")
            self._refresh_songs_list()

    def _open_playlist_folder(self):
        """Open the selected playlist folder in Finder/Explorer."""
        try:
            selected_item = self._pl_list.currentItem()
            if not selected_item:
                self.statusMsg.setText("Select a playlist first")
                return

            playlist_name = selected_item.text().split("\n")[0]
            safe_name = sanitize_filename(playlist_name, allow_spaces=True)
            playlist_folder = os.path.join(self.download_path, safe_name)

            if not os.path.isdir(playlist_folder):
                self.statusMsg.setText(f"Folder not found: {playlist_folder}")
                return

            # Open folder in system file manager
            import subprocess
            import sys
            if sys.platform == "darwin":
                subprocess.Popen(["open", playlist_folder])
            elif sys.platform == "win32":
                subprocess.Popen(f"explorer {playlist_folder}")
            else:
                subprocess.Popen(["xdg-open", playlist_folder])

            self.statusMsg.setText(f"Opening {safe_name}...")
        except Exception as e:
            self.statusMsg.setText(f"Error opening folder: {str(e)[:40]}")

    def _reveal_metadata_folder_main(self):
        """Open metadata folder in Finder/Explorer."""
        try:
            from Spotify_Downloader import _config_path
            import subprocess
            import sys

            config_path = _config_path()
            config_dir = os.path.dirname(config_path)

            if not os.path.isdir(config_dir):
                os.makedirs(config_dir, exist_ok=True)

            if sys.platform == "darwin":
                subprocess.Popen(["open", config_dir])
            elif sys.platform == "win32":
                subprocess.Popen(f"explorer {config_dir}")
            else:
                subprocess.Popen(["xdg-open", config_dir])

            self.statusMsg.setText("Opening metadata folder...")
        except Exception as e:
            self.statusMsg.setText(f"Error: {str(e)[:40]}")

    def _shift_main_content_for_sidebar(self):
        """Shift all main UI elements 280px to the right to make room for sidebar."""
        sidebar_width = 280

        # Shift main content widgets
        if hasattr(self, 'frame'):
            geo = self.frame.geometry()
            self.frame.setGeometry(geo.x() + sidebar_width, geo.y(), geo.width(), geo.height())

        if hasattr(self, 'SONGINFORMATION'):
            geo = self.SONGINFORMATION.geometry()
            self.SONGINFORMATION.setGeometry(geo.x() + sidebar_width, geo.y(), geo.width(), geo.height())

        # Shift any other main widgets
        if hasattr(self, 'label'):
            geo = self.label.geometry()
            self.label.setGeometry(geo.x() + sidebar_width, geo.y(), geo.width(), geo.height())

    def _refresh_playlist_list(self):
        """Repopulate QListWidget from config with checkboxes and destination paths."""
        self._pl_list.clear()
        for idx, entry in enumerate(load_saved_playlists(self._config)):
            name = entry.get("name") or "Loading..."
            # Extract playlist name from URL for display fallback
            if not entry.get("name"):
                try:
                    pid = extract_playlist_id(entry["url"])
                    # Fetch actual playlist name from Spotify in background
                    self._fetch_playlist_name_async(entry)
                except Exception:
                    pass

            # Build display text with name and final playlist folder path
            safe_name = sanitize_filename(name, allow_spaces=True)
            final_path = os.path.join(self.download_path, safe_name)
            display_text = f"{name}\n📁 {final_path}"
            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, entry["url"])
            item.setData(Qt.UserRole + 2, final_path)  # Store the final path for later use
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if entry.get("enabled", True) else Qt.Unchecked)
            item.setData(Qt.UserRole + 1, entry.get("enabled", True))
            self._pl_list.addItem(item)
            # Set first item as selected by default
            if idx == 0:
                self._pl_list.setCurrentItem(item)

    def _playlist_add(self):
        """Add the URL currently in PlaylistLink to the saved list."""
        url = self.PlaylistLink.text().strip()
        if not url:
            self.statusMsg.setText("Paste a playlist URL first")
            return
        try:
            url_type, _ = detect_spotify_url_type(url)
            if url_type != "playlist":
                self.statusMsg.setText("Only playlist URLs can be saved")
                return
        except ValueError as exc:
            self.statusMsg.setText(str(exc))
            return

        playlists = load_saved_playlists(self._config)
        if any(p["url"] == url for p in playlists):
            self.statusMsg.setText("Playlist already saved")
            return
        playlists.append({"url": url, "name": "", "enabled": True})
        save_saved_playlists(self._config, playlists)
        # Fetch playlist name in background
        self._fetch_playlist_name_async(playlists[-1])
        self._refresh_playlist_list()
        self.statusMsg.setText("Playlist saved")

    def _playlist_remove(self):
        """Remove selected playlist from the saved list and delete its songs data."""
        item = self._pl_list.currentItem()
        if not item:
            return
        playlist_name = item.text().split("\n")[0]
        url = item.data(Qt.UserRole)

        # Remove from saved playlists
        playlists = [p for p in load_saved_playlists(self._config) if p["url"] != url]
        save_saved_playlists(self._config, playlists)

        # Also delete the songs data for this playlist
        try:
            pid = extract_playlist_id(url)
            if "playlists_songs_data" in self._config and pid in self._config["playlists_songs_data"]:
                del self._config["playlists_songs_data"][pid]
                save_config(self._config)
        except Exception:
            pass

        self._refresh_playlist_list()
        self.statusMsg.setText(f"✓ Removed '{playlist_name}' & songs data → config.json saved")

    def _sync_single_playlist(self):
        """Sync (download missing tracks) for the currently selected playlist only."""
        selected_item = self._pl_list.currentItem()
        if not selected_item:
            self.statusMsg.setText("Select a playlist first")
            return

        if self._is_downloading:
            self.statusMsg.setText("A download is already in progress")
            return

        playlist_url = selected_item.data(Qt.UserRole)
        playlist_name = selected_item.text().split("\n")[0]

        # Create a single-playlist list for SyncAllThread
        playlist_entry = {"url": playlist_url, "name": playlist_name, "enabled": True}

        if not self._download_path_set:
            if not self._prompt_download_location():
                return
        if not self._ensure_download_path():
            self.statusMsg.setText("Cannot write to download folder")
            return

        self._cancel_event = threading.Event()
        self._is_downloading = True
        self.DownloadBtn.setText("Stop")
        self._sync_playlist_btn.setEnabled(False)

        self._sync_progress_bar.setVisible(True)
        self._sync_progress_bar.setValue(0)
        self._sync_progress_bar.setMaximum(100)
        self._sync_phase_label.setText(f"Starting sync: {playlist_name}...")

        self._sync_thread = SyncAllThread(
            [playlist_entry],
            self.download_path,
            self._cancel_event,
            audio_format=self._config.get("format", "mp3"),
            audio_quality=self._config.get("quality", "192"),
            filename_pattern=self._config.get("filename_pattern", "{title} - {artist}"),
            config=self._config,
        )
        self._sync_thread.sync_progress.connect(lambda msg: self.statusMsg.setText(msg))
        self._sync_thread.sync_progress.connect(self._update_sync_progress)
        self._sync_thread.sync_progress_count.connect(self._update_progress_bar)
        self._sync_thread.sync_done.connect(self._sync_finished_single)
        self._sync_thread.playlist_started.connect(
            lambda name, idx: self.update_AlbumName(f"Syncing: {name}")
        )
        self._sync_thread.song_meta_for_tags.connect(self.add_song_META, Qt.QueuedConnection)
        self._sync_thread.finished.connect(self.thread_finished)
        self._sync_thread.start()

    def _sync_finished_single(self, message: str):
        """Called when single playlist sync completes."""
        self._sync_progress_bar.setVisible(False)
        self._sync_phase_label.setText("")
        self.statusMsg.setText(message)
        self._sync_playlist_btn.setEnabled(True)
        self._is_downloading = False
        self.DownloadBtn.setText("Download")
        # Refresh songs list to show newly downloaded files
        if hasattr(self, '_current_view') and self._current_view == "fix_songs":
            self._refresh_songs_list()

    def _playlist_sync_all(self):
        """Kick off SyncAllThread for checked playlists only."""
        if self._is_downloading:
            self.statusMsg.setText("A download is already in progress")
            return
        all_playlists = load_saved_playlists(self._config)
        playlists = [p for p in all_playlists if p.get("enabled", True)]
        if not playlists:
            self.statusMsg.setText("No playlists selected for sync")
            return
        if not self._download_path_set:
            if not self._prompt_download_location():
                return
        if not self._ensure_download_path():
            self.statusMsg.setText("Cannot write to download folder")
            return

        self._cancel_event = threading.Event()
        self._is_downloading = True
        self.DownloadBtn.setText("Stop")
        self._pl_sync_btn.setEnabled(False)

        self._sync_progress_bar.setVisible(True)
        self._sync_progress_bar.setValue(0)
        self._sync_progress_bar.setMaximum(100)
        self._sync_phase_label.setText("Starting sync...")

        self._sync_thread = SyncAllThread(
            playlists,
            self.download_path,
            self._cancel_event,
            audio_format=self._config.get("format", "mp3"),
            audio_quality=self._config.get("quality", "192"),
            filename_pattern=self._config.get("filename_pattern", "{title} - {artist}"),
            config=self._config,
        )
        self._sync_thread.sync_progress.connect(lambda msg: self.statusMsg.setText(msg))
        self._sync_thread.sync_progress.connect(self._update_sync_progress)
        self._sync_thread.sync_progress_count.connect(self._update_progress_bar)
        self._sync_thread.sync_done.connect(self._sync_finished)
        self._sync_thread.playlist_started.connect(
            lambda name, idx: self.update_AlbumName(f"Syncing: {name}")
        )
        # Connect metadata signal for writing tags to existing/new files
        self._sync_thread.song_meta_for_tags.connect(self.add_song_META, Qt.QueuedConnection)
        self._sync_thread.finished.connect(self.thread_finished)
        self._sync_thread.start()

        # Switch to download view to show sync progress
        self._show_view("download")

    def _update_progress_bar(self, current: int, total: int):
        """Update progress bar with track count."""
        if total > 0:
            percent = int((current / total) * 100)
            self._sync_progress_bar.setValue(percent)
            self._sync_phase_label.setText(f"Downloading track {current}/{total}")
        else:
            self._sync_progress_bar.setValue(0)

    def _update_sync_progress(self, msg: str):
        """Update sync progress display with phase info."""
        self.statusMsg.setText(msg)
        # Parse progress info if it contains count indicators
        if "Syncing" in msg or "Downloaded" in msg or "Error" in msg:
            self._sync_phase_label.setText(msg.split(":")[0] if ":" in msg else "")

    def _sync_finished(self, message: str):
        """Called when sync completes."""
        self._sync_progress_bar.setVisible(False)
        self._sync_phase_label.setText("")
        self.statusMsg.setText(message)
        self._pl_sync_btn.setEnabled(True)
        # Refresh songs list to show newly downloaded files
        if hasattr(self, '_current_view') and self._current_view == "fix_songs":
            self._refresh_songs_list()

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
                filename_pattern=self._config.get("filename_pattern", "{title} - {artist}"),
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
        if self._sync_thread and self._sync_thread.isRunning():
            self._sync_thread.request_cancel()

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
        # Use config preference (add_meta_tags) which persists across sessions
        # This allows metadata to be added to existing files when enabled after downloading
        should_add_metadata = self._config.get("add_meta_tags", True)
        if should_add_metadata:
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
        if event.button() == Qt.LeftButton:
            self.m_drag = True
            self.m_DragPosition = event.globalPos() - self.pos()
            event.accept()
            self.setCursor(QCursor(Qt.ClosedHandCursor))

    def mouseMoveEvent(self, QMouseEvent):
        try:
            if Qt.LeftButton and self.m_drag:
                self.move(QMouseEvent.globalPos() - self.m_DragPosition)
                QMouseEvent.accept()
        except AttributeError:
            pass

    def mouseReleaseEvent(self, QMouseEvent):
        self.m_drag = False
        self.setCursor(QCursor(Qt.ArrowCursor))

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

    def _show_view(self, view_name):
        """Switch between views: 'home', 'download', 'add_playlist', 'settings', 'fix_songs'."""
        # Hide all content panels and main download UI
        if hasattr(self, '_home_panel'):
            self._home_panel.hide()
        if hasattr(self, '_add_playlist_panel'):
            self._add_playlist_panel.hide()
        if hasattr(self, '_settings_panel'):
            self._settings_panel.hide()
        if hasattr(self, '_fix_songs_panel'):
            self._fix_songs_panel.hide()
        if hasattr(self, 'frame'):
            self.frame.hide()
        if hasattr(self, 'SONGINFORMATION'):
            self.SONGINFORMATION.hide()

        # Show the selected view
        if view_name == "add_playlist":
            self._add_playlist_panel.show()
            self._add_pl_input.setFocus()
            self._add_pl_input.selectAll()
        elif view_name == "settings":
            self._settings_panel.show()
            self._pattern_field.setFocus()
            # Sync checkbox with main UI state
            if hasattr(self, 'AddMetaDataCheck'):
                self._settings_meta_check.blockSignals(True)
                self._settings_meta_check.setChecked(self.AddMetaDataCheck.isChecked())
                self._settings_meta_check.blockSignals(False)
        elif view_name == "fix_songs":
            self._fix_songs_panel.show()
        elif view_name == "download":
            # Show download view with frame and song information
            if hasattr(self, 'frame'):
                self.frame.show()
            if hasattr(self, 'SONGINFORMATION'):
                self.SONGINFORMATION.show()
            # Sync checkbox state from settings panel back to main UI
            if hasattr(self, '_settings_meta_check') and hasattr(self, 'AddMetaDataCheck'):
                self.AddMetaDataCheck.blockSignals(True)
                self.AddMetaDataCheck.setChecked(self._settings_meta_check.isChecked())
                self.AddMetaDataCheck.blockSignals(False)
        else:
            # Default: show home view
            if hasattr(self, '_home_panel'):
                self._home_panel.show()

        self._current_view = view_name

    def _get_playlist_songs_data(self, playlist_id):
        """Load persisted song data for a playlist from config."""
        playlists_data = self._config.get("playlists_songs_data", {})
        return playlists_data.get(playlist_id, [])

    def _save_playlist_songs_data(self, playlist_id, songs_data):
        """Persist song data for a playlist in config."""
        if "playlists_songs_data" not in self._config:
            self._config["playlists_songs_data"] = {}
        self._config["playlists_songs_data"][playlist_id] = songs_data
        save_config(self._config)

    def _get_expected_filename(self, song, track_num):
        """Get the expected filename using the module-level function. Single source of truth."""
        pattern = self._config.get("filename_pattern", "{title} - {artist}")
        fmt = self._config.get("format", "mp3")
        return get_expected_filename(song, track_num, pattern, fmt)

    def _fetch_from_spotify(self):
        """Fetch latest playlist from Spotify, merge with local data."""
        selected_item = self._pl_list.currentItem()
        if not selected_item:
            self.statusMsg.setText("Select a playlist first")
            return

        playlist_url = selected_item.data(Qt.UserRole)
        playlist_name = selected_item.text().split("\n")[0]

        try:
            pid = extract_playlist_id(playlist_url)
            client = PlaylistClient()

            # Get local persisted data
            local_songs = self._get_playlist_songs_data(pid)
            local_ids = {s.get("spotify_id") for s in local_songs if s.get("spotify_id")}

            # Fetch from Spotify
            spotify_tracks = []
            for track in client.iter_playlist_tracks(pid):
                spotify_tracks.append(track)

            # Merge: keep local youtube_urls, add new songs
            updated_songs = []
            for track in spotify_tracks:
                # Check if song exists in local data
                local_song = next((s for s in local_songs if s.get("spotify_id") == track.id), None)
                song_data = {
                    "spotify_id": track.id,
                    "track_url": f"https://open.spotify.com/track/{track.id}",
                    "title": track.title,
                    "artists": normalize_artist_string(track.artists),
                    "album": track.album or "",
                    "release_date": track.release_date or "",
                    "duration_ms": track.duration_ms or 0,
                    "youtube_url": local_song.get("youtube_url", "") if local_song else "",
                    "preview_url": track.preview_url or ""
                }
                updated_songs.append(song_data)

            # Save merged data to config.json
            self._save_playlist_songs_data(pid, updated_songs)
            self._refresh_songs_list()
            self.statusMsg.setText(f"✓ Synced {len(updated_songs)} songs from Spotify → config.json saved")
        except Exception as e:
            self.statusMsg.setText(f"⚠️ Error: {str(e)[:60]}")

    def _fetch_youtube_urls(self):
        """Search YouTube for songs without URLs in background."""
        selected_item = self._pl_list.currentItem()
        if not selected_item:
            self.statusMsg.setText("Select a playlist first")
            return

        playlist_url = selected_item.data(Qt.UserRole)

        try:
            pid = extract_playlist_id(playlist_url)
            songs_data = self._get_playlist_songs_data(pid)

            if not songs_data:
                self.statusMsg.setText("No songs found - fetch from Spotify first")
                return

            # Find songs without YouTube URLs
            songs_to_search = [s for s in songs_data if not s.get("youtube_url")]

            if not songs_to_search:
                self.statusMsg.setText("✓ All songs already have YouTube URLs!")
                return

            self.statusMsg.setText(f"🔍 Searching YouTube for {len(songs_to_search)} songs...")

            # Start background thread for YouTube search
            self._yt_fetch_thread = YouTubeFetchThread(songs_data, pid)
            self._yt_fetch_thread.progress.connect(lambda msg: self._on_yt_progress(msg, pid))
            self._yt_fetch_thread.finished_signal.connect(
                lambda found: self._yt_fetch_complete(pid, found)
            )
            self._yt_fetch_thread.start()

        except Exception as e:
            self.statusMsg.setText(f"⚠️ Error: {str(e)[:60]}")

    def _on_yt_progress(self, message: str, playlist_id):
        """Update status and refresh table as YouTube URLs are found."""
        self.statusMsg.setText(message)
        # Refresh songs list if viewing it and this is the selected playlist
        if hasattr(self, '_current_view') and self._current_view == "fix_songs":
            selected_item = self._pl_list.currentItem()
            if selected_item:
                selected_url = selected_item.data(Qt.UserRole)
                try:
                    selected_pid = extract_playlist_id(selected_url)
                    if selected_pid == playlist_id:
                        self._refresh_songs_list()
                except Exception:
                    pass

    def _yt_fetch_complete(self, playlist_id, found_count):
        """Called when YouTube fetch completes."""
        songs_data = self._get_playlist_songs_data(playlist_id)
        self._save_playlist_songs_data(playlist_id, songs_data)
        self._refresh_songs_list()
        self.statusMsg.setText(f"✓ Found {found_count} YouTube URLs → config.json saved")

    def _show_playlist_songs(self):
        """Show songs from selected playlist with Spotify/YouTube links."""
        self._show_view("fix_songs")
        self._refresh_songs_list()

    def _refresh_songs_list(self):
        """Load and display songs with state indicators (Spotify/Local/Disk)."""
        self._songs_table.setRowCount(0)
        selected_item = self._pl_list.currentItem()
        if not selected_item:
            self._fix_playlist_label.setText("❌ No playlist selected")
            self._fix_playlist_label.setStyleSheet("color: #ff9800; font-size: 12px; font-weight: bold;")
            return

        playlist_url = selected_item.data(Qt.UserRole)
        playlist_name = selected_item.text().split("\n")[0]

        # Update the playlist label
        self._fix_playlist_label.setText(f"📋 {playlist_name}")
        self._fix_playlist_label.setStyleSheet("color: #4CAF50; font-size: 12px; font-weight: bold;")

        try:
            pid = extract_playlist_id(playlist_url)
            songs_data = self._get_playlist_songs_data(pid)

            if not songs_data:
                self._fix_playlist_label.setText(f"📋 {playlist_name} (no data - click 'Fetch from Spotify')")
                return

            # Construct playlist folder to check disk state
            safe_name = sanitize_filename(playlist_name, allow_spaces=True)
            playlist_folder = os.path.join(self.download_path, safe_name)

            self._songs_table.setRowCount(len(songs_data))
            for idx, song in enumerate(songs_data):
                sp_id = song.get("spotify_id")
                title = song.get("title", "Unknown")
                yt_url = song.get("youtube_url", "")

                # Check disk state: build expected filename and check if it exists
                disk_state = self._check_file_on_disk(song, playlist_folder, idx + 1)

                # Col 0: Song name with state indicators
                spotify_state = "✓" if song.get("spotify_id") else "✗"
                local_state = "✓" if yt_url else "✗"
                disk_indicator = "✓" if disk_state else "✗"

                artists = song.get("artists", "Unknown")
                name_text = f"{artists} - {title}"
                state_text = f"{name_text}\n[S:{spotify_state} L:{local_state} D:{disk_indicator}]"
                name_item = QTableWidgetItem(state_text)
                name_item.setData(Qt.UserRole, sp_id)
                name_item.setForeground(QColor("white"))
                font = QFont()
                font.setPointSize(10)
                name_item.setFont(font)
                self._songs_table.setItem(idx, 0, name_item)

                # Col 1: Spotify actions + duration (all on one line)
                spotify_container = QFrame()
                spotify_layout = QHBoxLayout(spotify_container)
                spotify_layout.setContentsMargins(2, 2, 2, 2)
                spotify_layout.setSpacing(2)

                spotify_open_btn = QPushButton("🔗")
                spotify_open_btn.setStyleSheet("background: #1DB954; color: white; border: none; padding: 4px; border-radius: 2px; font-size: 10px;")
                spotify_open_btn.setMaximumWidth(30)
                spotify_open_btn.setToolTip("Open on Spotify")
                spotify_open_btn.clicked.connect(lambda checked, tid=sp_id: webbrowser.open(f"https://open.spotify.com/track/{tid}"))
                spotify_layout.addWidget(spotify_open_btn)

                preview_url = song.get("preview_url", "")
                if preview_url:
                    preview_btn = QPushButton("🔊")
                    preview_btn.setStyleSheet("background: #1DB954; color: white; border: none; padding: 4px; border-radius: 2px; font-size: 10px;")
                    preview_btn.setMaximumWidth(30)
                    preview_btn.setToolTip("Preview")
                    preview_btn.clicked.connect(lambda checked, url=preview_url: self._play_audio_preview(url, "Spotify"))
                    spotify_layout.addWidget(preview_btn)

                # Duration label on same line as buttons
                duration_ms = song.get("duration_ms", 0)
                duration_text = format_duration(duration_ms)
                duration_label = QLabel(f"⏱ {duration_text}")
                duration_label.setStyleSheet("color: #aaa; font-size: 8px;")
                spotify_layout.addWidget(duration_label)

                # Edit metadata button
                edit_meta_btn = QPushButton("✎")
                edit_meta_btn.setStyleSheet("background: #FF9800; color: white; border: none; padding: 4px; border-radius: 2px; font-size: 10px;")
                edit_meta_btn.setMaximumWidth(30)
                edit_meta_btn.setToolTip("Edit title/artist")
                edit_meta_btn.clicked.connect(lambda checked, song_obj=song, pid=pid: self._show_edit_metadata_dialog(song_obj, pid))
                spotify_layout.addWidget(edit_meta_btn)

                self._songs_table.setCellWidget(idx, 1, spotify_container)

                # Col 2: YouTube + Local data
                yt_container = QFrame()
                yt_layout = QHBoxLayout(yt_container)
                yt_layout.setContentsMargins(2, 2, 2, 2)
                yt_layout.setSpacing(2)

                if yt_url:
                    yt_open_btn = QPushButton("▶")
                    yt_open_btn.setStyleSheet("background: #FF0000; color: white; border: none; padding: 4px 6px; border-radius: 2px; font-size: 9px;")
                    yt_open_btn.setMaximumWidth(30)
                    yt_open_btn.clicked.connect(lambda checked, url=yt_url: webbrowser.open(url))
                    yt_layout.addWidget(yt_open_btn)

                    edit_btn = QPushButton("✎")
                    edit_btn.setStyleSheet("background: #2196F3; color: white; border: none; padding: 4px; border-radius: 2px; font-size: 10px;")
                    edit_btn.setMaximumWidth(30)
                    edit_btn.setToolTip("Edit YouTube URL")
                    edit_btn.clicked.connect(lambda checked, sid=sp_id, t=title, pid=pid: self._show_edit_dialog(sid, t, pid))
                    yt_layout.addWidget(edit_btn)

                    clear_btn = QPushButton("✕")
                    clear_btn.setStyleSheet("background: #F44336; color: white; border: none; padding: 4px; border-radius: 2px; font-size: 10px;")
                    clear_btn.setMaximumWidth(30)
                    clear_btn.setToolTip("Clear YouTube URL")
                    clear_btn.clicked.connect(lambda checked, sid=sp_id, t=title, pid=pid: self._clear_youtube_url(sid, t, pid))
                    yt_layout.addWidget(clear_btn)
                else:
                    edit_btn = QPushButton("✎")
                    edit_btn.setStyleSheet("background: #2196F3; color: white; border: none; padding: 4px; border-radius: 2px; font-size: 10px;")
                    edit_btn.setMaximumWidth(30)
                    edit_btn.setToolTip("Edit YouTube URL")
                    edit_btn.clicked.connect(lambda checked, sid=sp_id, t=title, pid=pid: self._show_edit_dialog(sid, t, pid))
                    yt_layout.addWidget(edit_btn)

                    find_btn = QPushButton("🔍")
                    find_btn.setStyleSheet("background: #FF9800; color: white; border: none; padding: 4px; border-radius: 2px; font-size: 10px;")
                    find_btn.setMaximumWidth(30)
                    find_btn.setToolTip("Find YouTube URL")
                    find_btn.clicked.connect(lambda checked, sid=sp_id, t=title, pid=pid: self._find_youtube_url_for_track(sid, t, pid))
                    yt_layout.addWidget(find_btn)

                self._songs_table.setCellWidget(idx, 2, yt_container)

                # Col 3: Disk - filename, duration, and actions
                disk_container = QFrame()
                disk_layout = QVBoxLayout(disk_container)
                disk_layout.setContentsMargins(2, 2, 2, 2)
                disk_layout.setSpacing(2)

                # Get the expected filename (single source of truth)
                expected_filename = self._get_expected_filename(song, idx + 1)

                # Filename label
                filename_label = QLabel(expected_filename)
                filename_label.setStyleSheet("color: #aaa; font-size: 8px; font-weight: bold;")
                filename_label.setWordWrap(True)
                disk_layout.addWidget(filename_label)

                if disk_state:
                    # Duration if available
                    disk_duration = song.get("disk_file_duration")
                    if disk_duration:
                        duration_label = QLabel(format_duration(disk_duration))
                        duration_label.setStyleSheet("color: #4CAF50; font-size: 8px;")
                        disk_layout.addWidget(duration_label)

                    # Buttons row
                    buttons_layout = QHBoxLayout()
                    buttons_layout.setContentsMargins(0, 0, 0, 0)
                    buttons_layout.setSpacing(2)

                    # View tags button
                    tags_btn = QPushButton("🏷")
                    tags_btn.setStyleSheet("background: #9C27B0; color: white; border: none; padding: 4px; border-radius: 2px; font-size: 10px;")
                    tags_btn.setMaximumWidth(30)
                    tags_btn.setToolTip("View/Edit ID3 tags")
                    expected_filepath = os.path.join(
                        os.path.join(self.download_path, sanitize_filename(playlist_name, allow_spaces=True)),
                        self._get_expected_filename(song, idx + 1)
                    )
                    tags_btn.clicked.connect(lambda checked, fpath=expected_filepath, song_obj=song: self._show_tags_dialog(fpath, song_obj))
                    buttons_layout.addWidget(tags_btn)

                    # Redownload button
                    redownload_btn = QPushButton("⬇️")
                    redownload_btn.setStyleSheet("background: #2196F3; color: white; border: none; padding: 4px; border-radius: 2px; font-size: 10px;")
                    redownload_btn.setMaximumWidth(30)
                    redownload_btn.setToolTip("Redownload (delete & re-download)")
                    redownload_btn.clicked.connect(lambda checked, song_obj=song, t_num=idx+1: self._redownload_track(song_obj, t_num))
                    buttons_layout.addWidget(redownload_btn)

                    # Delete button
                    delete_btn = QPushButton("🗑")
                    delete_btn.setStyleSheet("background: #F44336; color: white; border: none; padding: 4px; border-radius: 2px; font-size: 10px;")
                    delete_btn.setMaximumWidth(30)
                    delete_btn.setToolTip("Delete file")
                    delete_btn.clicked.connect(lambda checked, song_obj=song, t_num=idx+1: self._delete_track_file(song_obj, t_num))
                    buttons_layout.addWidget(delete_btn)

                    disk_layout.addLayout(buttons_layout)
                else:
                    # Download button
                    download_btn = QPushButton("⬇️ Download")
                    download_btn.setStyleSheet("background: #4CAF50; color: white; border: none; padding: 4px 6px; border-radius: 2px; font-size: 9px;")
                    download_btn.setMaximumWidth(100)
                    download_btn.clicked.connect(lambda checked, song_obj=song, t_num=idx+1: self._download_single_track(song_obj, t_num))
                    disk_layout.addWidget(download_btn)

                self._songs_table.setCellWidget(idx, 3, disk_container)

            self._songs_table.setRowHeight(0, 40)
            for i in range(len(songs_data)):
                self._songs_table.setRowHeight(i, 40)

            self.statusMsg.setText(f"✓ Loaded {len(songs_data)} songs")
        except Exception as e:
            print(f"[ERROR] _refresh_songs_list: {e}")
            import traceback
            traceback.print_exc()
            self.statusMsg.setText(f"⚠️ Error: {str(e)[:60]}")

    def _show_edit_dialog(self, track_id, track_title, playlist_id):
        """Show dialog to set/edit YouTube URL for a track."""
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Set YouTube URL - {track_title[:40]}")
        dialog.setGeometry(400, 250, 550, 180)
        dialog.setStyleSheet("QDialog { background: rgba(40,40,40,255); } QLabel { color: white; } QLineEdit { background: white; color: black; border: 1px solid #999; padding: 6px; border-radius: 3px; font-size: 11px; }")

        layout = QVBoxLayout(dialog)

        info = QLabel(f"Track: {track_title[:40]}\n\nEnter YouTube URL:")
        info.setStyleSheet("color: #aaa; font-size: 10px;")
        layout.addWidget(info)

        url_input = QLineEdit()
        url_input.setPlaceholderText("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        layout.addWidget(url_input)

        buttons_layout = QHBoxLayout()
        save_btn = QPushButton("💾 Save")
        save_btn.setStyleSheet("background: #4CAF50; color: white; border: none; padding: 8px 16px; border-radius: 3px; font-weight: bold;")
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("background: #666; color: white; border: none; padding: 8px 16px; border-radius: 3px;")

        buttons_layout.addWidget(save_btn)
        buttons_layout.addWidget(cancel_btn)
        layout.addLayout(buttons_layout)

        cancel_btn.clicked.connect(dialog.reject)
        save_btn.clicked.connect(lambda: self._save_youtube_url(track_id, url_input.text(), dialog, track_title, playlist_id))

        dialog.exec_()

    def _show_edit_metadata_dialog(self, song, playlist_id):
        """Show dialog to edit song title and artist."""
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Edit Metadata - {song.get('title', '')[:40]}")
        dialog.setGeometry(400, 250, 500, 200)
        dialog.setStyleSheet("QDialog { background: rgba(40,40,40,255); } QLabel { color: white; } QLineEdit { background: white; color: black; border: 1px solid #999; padding: 6px; border-radius: 3px; font-size: 11px; }")

        layout = QVBoxLayout(dialog)

        # Title field
        title_label = QLabel("Title:")
        title_label.setStyleSheet("color: #aaa; font-size: 10px;")
        layout.addWidget(title_label)
        title_input = QLineEdit()
        title_input.setText(song.get("title", ""))
        layout.addWidget(title_input)

        # Artist field
        artist_label = QLabel("Artist:")
        artist_label.setStyleSheet("color: #aaa; font-size: 10px;")
        layout.addWidget(artist_label)
        artist_input = QLineEdit()
        artist_input.setText(song.get("artists", ""))
        layout.addWidget(artist_input)

        # Buttons
        buttons_layout = QHBoxLayout()
        save_btn = QPushButton("💾 Save")
        save_btn.setStyleSheet("background: #4CAF50; color: white; border: none; padding: 8px 16px; border-radius: 3px; font-weight: bold;")
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("background: #666; color: white; border: none; padding: 8px 16px; border-radius: 3px;")

        buttons_layout.addWidget(save_btn)
        buttons_layout.addWidget(cancel_btn)
        layout.addLayout(buttons_layout)

        cancel_btn.clicked.connect(dialog.reject)
        save_btn.clicked.connect(lambda: self._save_metadata(song, title_input.text(), artist_input.text(), playlist_id, dialog))

        dialog.exec_()

    def _save_metadata(self, song, title, artist, playlist_id, dialog):
        """Save edited metadata to config."""
        try:
            songs_data = self._get_playlist_songs_data(playlist_id)

            # Find and update the song
            for s in songs_data:
                if s.get("spotify_id") == song.get("spotify_id"):
                    if title.strip():
                        s["title"] = title.strip()
                    if artist.strip():
                        s["artists"] = artist.strip()
                    self._save_playlist_songs_data(playlist_id, songs_data)
                    self._refresh_songs_list()
                    self.statusMsg.setText(f"✓ Metadata saved")
                    dialog.accept()
                    return

        except Exception as e:
            self.statusMsg.setText(f"❌ Error: {str(e)[:40]}")

    def _show_tags_dialog(self, filepath, song):
        """Show dialog to view and edit ALL ID3 tags from file in a single table."""
        if not os.path.isfile(filepath):
            self.statusMsg.setText(f"❌ File not found: {filepath}")
            return

        # Read tags from file
        file_tags = read_id3_tags(filepath)

        dialog = QDialog(self)
        dialog.setWindowTitle(f"ID3 Tags - {song.get('title', '')[:40]}")
        dialog.setGeometry(200, 50, 1100, 750)
        dialog.setStyleSheet("QDialog { background: rgba(40,40,40,255); } QLabel { color: white; } QLineEdit { background: white; color: black; border: 1px solid #999; padding: 4px; border-radius: 2px; font-size: 9px; } QTableWidget { background: rgba(0,0,0,100); color: white; gridline-color: rgba(255,255,255,20); } QHeaderView::section { background: rgba(100,100,100,200); color: white; padding: 4px; }")

        layout = QVBoxLayout(dialog)

        # Info label
        info = QLabel(f"File: {os.path.basename(filepath)}")
        info.setStyleSheet("color: #aaa; font-size: 10px; font-weight: bold;")
        layout.addWidget(info)

        # Build combined tag list with version info
        all_tags = {}
        for version in ["ID3v2.4", "ID3v2.3", "ID3v1"]:
            if version not in ID3_STANDARD_FRAMES:
                continue
            for frame_id, pretty_name in ID3_STANDARD_FRAMES[version].items():
                if frame_id not in ["APIC", "TXXX"] and frame_id not in all_tags:
                    all_tags[frame_id] = {"name": pretty_name, "version": version}

        # Create single table for all standard tags
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Frame ID", "Tag Name", "ID3 Version", "Value"])
        table.horizontalHeader().setStretchLastSection(True)
        table.setColumnWidth(0, 80)
        table.setColumnWidth(1, 200)
        table.setColumnWidth(2, 100)

        tag_inputs = {}
        row = 0

        # Add all standard tags (sorted)
        for frame_id, info in sorted(all_tags.items()):
            table.insertRow(row)
            value = file_tags.get(frame_id, "")

            # Frame ID
            id_item = QTableWidgetItem(frame_id)
            id_item.setForeground(QColor("#FF9800"))
            table.setItem(row, 0, id_item)

            # Tag Name
            name_item = QTableWidgetItem(info["name"])
            name_item.setForeground(QColor("#aaa"))
            table.setItem(row, 1, name_item)

            # ID3 Version
            version_item = QTableWidgetItem(info["version"])
            version_item.setForeground(QColor("#4CAF50"))
            table.setItem(row, 2, version_item)

            # Value (editable)
            input_field = QLineEdit()
            input_field.setText(str(value))
            if value:
                input_field.setStyleSheet("background: white; color: black;")
            else:
                input_field.setStyleSheet("background: #444; color: #999;")
            table.setCellWidget(row, 3, input_field)
            tag_inputs[frame_id] = input_field

            row += 1

        table.setRowCount(row)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(table)

        # Custom tags section
        custom_label = QLabel("▼ Custom Tags (TXXX)")
        custom_label.setStyleSheet("color: #FF9800; font-size: 11px; font-weight: bold; margin-top: 10px;")
        layout.addWidget(custom_label)

        # Custom tags table
        custom_table = QTableWidget()
        custom_table.setColumnCount(4)
        custom_table.setHorizontalHeaderLabels(["Frame ID", "Description", "ID3 Version", "Value"])
        custom_table.horizontalHeader().setStretchLastSection(True)
        custom_table.setColumnWidth(0, 80)
        custom_table.setColumnWidth(1, 200)
        custom_table.setColumnWidth(2, 100)
        custom_table.setMaximumHeight(150)

        custom_row = 0
        for frame_id, value in sorted(file_tags.items()):
            if frame_id.startswith("TXXX"):
                custom_table.insertRow(custom_row)

                # Frame ID
                id_item = QTableWidgetItem(frame_id)
                id_item.setForeground(QColor("#FF9800"))
                custom_table.setItem(custom_row, 0, id_item)

                # Description
                desc_item = QTableWidgetItem(frame_id.replace("TXXX:", ""))
                desc_item.setForeground(QColor("#aaa"))
                custom_table.setItem(custom_row, 1, desc_item)

                # Version
                version_item = QTableWidgetItem("v2.4+")
                version_item.setForeground(QColor("#4CAF50"))
                custom_table.setItem(custom_row, 2, version_item)

                # Value (editable)
                input_field = QLineEdit()
                input_field.setText(str(value))
                input_field.setStyleSheet("background: white; color: black;")
                custom_table.setCellWidget(custom_row, 3, input_field)
                tag_inputs[frame_id] = input_field

                custom_row += 1

        custom_table.setRowCount(custom_row)
        custom_table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(custom_table)

        # Buttons
        buttons_layout = QHBoxLayout()
        save_btn = QPushButton("💾 Save Tags")
        save_btn.setStyleSheet("background: #4CAF50; color: white; border: none; padding: 8px 16px; border-radius: 3px; font-weight: bold;")
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet("background: #666; color: white; border: none; padding: 8px 16px; border-radius: 3px;")

        buttons_layout.addWidget(save_btn)
        buttons_layout.addWidget(close_btn)
        layout.addLayout(buttons_layout)

        close_btn.clicked.connect(dialog.reject)
        save_btn.clicked.connect(lambda: self._save_id3_tags(filepath, tag_inputs, dialog))

        dialog.exec_()

    def _save_id3_tags(self, filepath, tag_inputs, dialog):
        """Save edited ID3 tags back to the MP3 file."""
        try:
            from mutagen.id3._frames import TXXX
            import mutagen.id3._frames as frames_module

            # Load existing ID3 tags
            try:
                id3 = ID3(filepath)
            except Exception:
                id3 = ID3()

            # Update each frame with new values
            for frame_id, widget in tag_inputs.items():
                value = widget.text().strip()

                # Handle custom TXXX frames (e.g., "TXXX:YouTubeURL")
                if frame_id.startswith("TXXX:"):
                    if value:
                        desc = frame_id.replace("TXXX:", "")
                        id3[frame_id] = TXXX(encoding=3, desc=desc, text=[value])
                    elif frame_id in id3:
                        del id3[frame_id]
                # Handle standard text frames (T** format)
                elif frame_id.startswith("T") and len(frame_id) == 4:
                    # Get the frame class from mutagen.id3._frames (e.g., TIT2, TPE1)
                    frame_cls = getattr(frames_module, frame_id, None)
                    if value:
                        if frame_cls:
                            id3[frame_id] = frame_cls(encoding=3, text=[value])
                        else:
                            # Fallback for unknown frame types
                            from mutagen.id3._frames import TextFrame
                            id3[frame_id] = TextFrame(frame_id, encoding=3, text=[value])
                    elif frame_id in id3:
                        del id3[frame_id]

            # Save the modified ID3 tag to file
            id3.save(filepath, v2_version=4)

            self.statusMsg.setText(f"✓ Tags saved to {os.path.basename(filepath)}")
            dialog.accept()
        except Exception as e:
            self.statusMsg.setText(f"❌ Error saving tags: {str(e)[:60]}")

    def _save_tags_to_file(self, filepath, tag_inputs, song, dialog):
        """Save edited tags back to the MP3 file."""
        try:
            tags_to_write = {}
            for tag_name, widget in tag_inputs.items():
                value = widget.text().strip()
                if value:
                    tags_to_write[tag_name] = value

            # Write tags using the standard function
            _write_metadata_mp3(filepath, tags_to_write, None)

            self.statusMsg.setText(f"✓ Tags saved to {os.path.basename(filepath)}")
            dialog.accept()
        except Exception as e:
            self.statusMsg.setText(f"❌ Error saving tags: {str(e)[:40]}")

    def _play_audio_preview(self, preview_url, source):
        """Play audio preview using system media player."""
        try:
            if source == "Spotify":
                webbrowser.open(preview_url)
                self.statusMsg.setText("Opening preview in browser...")
            else:
                webbrowser.open(preview_url)
        except Exception as e:
            self.statusMsg.setText(f"Could not play preview: {str(e)[:40]}")

    def _play_youtube(self, url):
        """Open YouTube video in browser for playback."""
        try:
            webbrowser.open(url)
            self.statusMsg.setText("▶ Opening YouTube in browser...")
        except Exception as e:
            self.statusMsg.setText(f"Error: {str(e)[:40]}")

    def _scan_disk_state(self):
        """Scan disk and update the file state indicators in the table."""
        self.statusMsg.setText("💾 Scanning disk...")
        self._refresh_songs_list()
        self.statusMsg.setText("✓ Disk scan complete")

    def _check_file_on_disk(self, song, playlist_folder, track_num):
        """Check if a track file exists on disk and update disk_file_duration."""
        try:
            # Get expected filename using single source of truth
            expected_filename = self._get_expected_filename(song, track_num)
            fmt = self._config.get("format", "mp3")

            # Check if file exists
            if os.path.isdir(playlist_folder):
                expected_path = os.path.join(playlist_folder, expected_filename)
                if os.path.isfile(expected_path):
                    # Read duration and update config
                    duration_ms = get_audio_duration_ms(expected_path)
                    if duration_ms > 0:
                        self._update_song_disk_duration(song, duration_ms)
                    return True

                # Also check for files with track ID suffix (collision handling)
                track_id = song.get("spotify_id", "")
                if track_id:
                    base = os.path.splitext(expected_filename)[0]
                    collision_path = os.path.join(playlist_folder, f"{base} [{track_id}].{fmt}")
                    if os.path.isfile(collision_path):
                        # Read duration and update config
                        duration_ms = get_audio_duration_ms(collision_path)
                        if duration_ms > 0:
                            self._update_song_disk_duration(song, duration_ms)
                        return True

                # Fallback: search for files containing both artist and title (handles spacing differences)
                title = song.get("title", "").lower()
                artists = song.get("artists", "").lower()
                if title and artists and os.path.isdir(playlist_folder):
                    try:
                        for filename in os.listdir(playlist_folder):
                            if filename.lower().endswith(f".{fmt}"):
                                name_lower = filename.lower()
                                # Check if both title and artist are in the filename
                                if title in name_lower and artists in name_lower:
                                    filepath = os.path.join(playlist_folder, filename)
                                    if os.path.isfile(filepath):
                                        # Read duration and update config
                                        duration_ms = get_audio_duration_ms(filepath)
                                        if duration_ms > 0:
                                            self._update_song_disk_duration(song, duration_ms)
                                        return True
                    except Exception:
                        pass

            return False
        except Exception as e:
            print(f"[DEBUG] Error checking disk: {e}")
            return False

    def _update_song_disk_duration(self, song, duration_ms):
        """Update disk_file_duration in config.json for a song."""
        try:
            pid = extract_playlist_id(self._pl_list.currentItem().data(Qt.UserRole))
            songs_data = self._get_playlist_songs_data(pid)
            spotify_id = song.get("spotify_id")

            for s in songs_data:
                if s.get("spotify_id") == spotify_id:
                    s["disk_file_duration"] = duration_ms
                    self._save_playlist_songs_data(pid, songs_data)
                    break
        except Exception as e:
            print(f"[DEBUG] Error updating disk duration: {e}")

    def _download_single_track(self, song, track_num):
        """Download a single track (for first-time download)."""
        try:
            selected_item = self._pl_list.currentItem()
            if not selected_item:
                self.statusMsg.setText("No playlist selected")
                return

            playlist_url = selected_item.data(Qt.UserRole)
            playlist_name = selected_item.text().split("\n")[0]
            track_url = song.get("track_url", "")

            if not track_url:
                self.statusMsg.setText("No track URL available")
                return

            self.statusMsg.setText(f"⬇️ Downloading '{song.get('title', 'Unknown')}'...")
            safe_name = sanitize_filename(playlist_name, allow_spaces=True)
            playlist_folder = os.path.join(self.download_path, safe_name)

            if not os.path.exists(playlist_folder):
                os.makedirs(playlist_folder)

            scraper = MusicScraper(
                cancel_event=self._cancel_event,
                audio_format=self._config.get("format", "mp3"),
                audio_quality=self._config.get("quality", "192"),
                filename_pattern=self._config.get("filename_pattern", "{title} - {artist}"),
            )

            # Download the track
            yt_url = song.get("youtube_url", "")
            result = scraper.scrape_track(track_url, playlist_folder, track_num=track_num, youtube_url=yt_url)

            if result:
                filepath, found_yt_url = result
                if filepath:
                    # Update song data in config
                    pid = extract_playlist_id(playlist_url)
                    songs_data = self._get_playlist_songs_data(pid)
                    for s in songs_data:
                        if s.get("spotify_id") == song.get("spotify_id"):
                            if found_yt_url and not s.get("youtube_url"):
                                s["youtube_url"] = found_yt_url
                            disk_duration = get_audio_duration_ms(filepath)
                            if disk_duration > 0:
                                s["disk_file_duration"] = disk_duration
                            self._save_playlist_songs_data(pid, songs_data)
                            break

                    self.statusMsg.setText(f"✓ Downloaded '{song.get('title', 'Unknown')}'")
                    self._refresh_songs_list()
                else:
                    self.statusMsg.setText(f"❌ Download failed for '{song.get('title', 'Unknown')}'")
            else:
                self.statusMsg.setText(f"❌ Download failed for '{song.get('title', 'Unknown')}'")

        except Exception as e:
            self.statusMsg.setText(f"❌ Error: {str(e)[:40]}")

    def _redownload_track(self, song, track_num):
        """Delete existing file and redownload the track."""
        try:
            selected_item = self._pl_list.currentItem()
            if not selected_item:
                self.statusMsg.setText("No playlist selected")
                return

            # First delete the existing file
            self._delete_track_file(song, track_num)
            # Then download it again
            self._download_single_track(song, track_num)

        except Exception as e:
            self.statusMsg.setText(f"❌ Error: {str(e)[:40]}")

    def _delete_track_file(self, song, track_num):
        """Delete a downloaded track file from disk and refresh UI."""
        try:
            selected_item = self._pl_list.currentItem()
            if not selected_item:
                self.statusMsg.setText("No playlist selected")
                return

            playlist_name = selected_item.text().split("\n")[0]
            safe_name = sanitize_filename(playlist_name, allow_spaces=True)
            playlist_folder = os.path.join(self.download_path, safe_name)

            if not os.path.isdir(playlist_folder):
                self.statusMsg.setText("Playlist folder not found")
                return

            # Get the expected filename using single source of truth
            expected_filename = self._get_expected_filename(song, track_num)
            fmt = self._config.get("format", "mp3")

            # Try exact match first
            filepath = os.path.join(playlist_folder, expected_filename)
            if os.path.isfile(filepath):
                os.remove(filepath)
                self.statusMsg.setText(f"🗑 Deleted '{song.get('title', 'Unknown')}'")
                self._refresh_songs_list()
                return

            # Try collision-handled version
            track_id = song.get("spotify_id", "")
            if track_id:
                base = os.path.splitext(expected_filename)[0]
                collision_path = os.path.join(playlist_folder, f"{base} [{track_id}].{fmt}")
                if os.path.isfile(collision_path):
                    os.remove(collision_path)
                    self.statusMsg.setText(f"🗑 Deleted '{song.get('title', 'Unknown')}'")
                    self._refresh_songs_list()
                    return

            self.statusMsg.setText(f"❌ File not found for '{song.get('title', 'Unknown')}'")

        except Exception as e:
            self.statusMsg.setText(f"❌ Error: {str(e)[:40]}")

    def _clear_youtube_url(self, track_id, track_title, playlist_id):
        """Clear YouTube URL for a track."""
        try:
            songs_data = self._get_playlist_songs_data(playlist_id)
            for song in songs_data:
                if song.get("spotify_id") == track_id:
                    song["youtube_url"] = ""
                    self._save_playlist_songs_data(playlist_id, songs_data)
                    self._refresh_songs_list()
                    self.statusMsg.setText(f"✓ Cleared YouTube URL for {track_title[:30]}")
                    return
            self.statusMsg.setText(f"❌ Song not found")
        except Exception as e:
            self.statusMsg.setText(f"❌ Error: {str(e)[:40]}")

    def _find_youtube_url_for_track(self, track_id, track_title, playlist_id):
        """Find YouTube URL for a specific track."""
        try:
            from yt_dlp import YoutubeDL
            songs_data = self._get_playlist_songs_data(playlist_id)
            song = None
            for s in songs_data:
                if s.get("spotify_id") == track_id:
                    song = s
                    break

            if not song:
                self.statusMsg.setText(f"❌ Song not found")
                return

            if song.get("youtube_url"):
                self.statusMsg.setText(f"ℹ️ Already has YouTube URL")
                return

            self.statusMsg.setText(f"🔍 Searching YouTube for {track_title[:30]}...")

            title = song.get("title", "Unknown")
            artists = song.get("artists", "")
            search_query = f"{title} {artists} audio"

            try:
                ydl_opts = {
                    "quiet": True,
                    "no_warnings": True,
                    "default_search": "ytsearch1",
                    "socket_timeout": 10,
                }
                with YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(search_query, download=False)
                    if info and info.get("entries"):
                        yt_url = info["entries"][0].get("webpage_url")
                        if yt_url:
                            song["youtube_url"] = yt_url
                            self._save_playlist_songs_data(playlist_id, songs_data)
                            self._refresh_songs_list()
                            self.statusMsg.setText(f"✓ Found YouTube URL for {track_title[:30]}")
                            return
                self.statusMsg.setText(f"❌ No YouTube URL found for {track_title[:30]}")
            except Exception as e:
                self.statusMsg.setText(f"❌ Search error: {str(e)[:40]}")
        except Exception as e:
            self.statusMsg.setText(f"❌ Error: {str(e)[:40]}")

    def _save_youtube_url(self, track_id, youtube_url, dialog, track_title, playlist_id):
        """Save edited YouTube URL to persisted song data."""
        songs_data = self._get_playlist_songs_data(playlist_id)

        # Find and update the song
        for song in songs_data:
            if song.get("spotify_id") == track_id:
                if youtube_url.strip():
                    song["youtube_url"] = youtube_url
                    self._save_playlist_songs_data(playlist_id, songs_data)
                    self._refresh_songs_list()
                    self.statusMsg.setText(f"✓ YouTube URL saved for {track_title[:30]}")
                    dialog.accept()
                else:
                    QMessageBox.warning(self, "Invalid URL", "Please enter a valid YouTube URL")
                return

    def _add_new_playlist(self):
        """Add a new playlist from the URL input in add_playlist_panel."""
        url = self._add_pl_input.text().strip()
        if not url:
            self.statusMsg.setText("Please enter a playlist URL")
            return

        try:
            url_type, _ = detect_spotify_url_type(url)
            if url_type != "playlist":
                self.statusMsg.setText("Only playlist URLs can be saved")
                return
        except ValueError as exc:
            self.statusMsg.setText(str(exc))
            return

        playlists = load_saved_playlists(self._config)
        if any(p["url"] == url for p in playlists):
            self.statusMsg.setText("Playlist already saved")
            return

        playlists.append({"url": url, "name": "", "enabled": True})
        save_saved_playlists(self._config, playlists)
        self._fetch_playlist_name_async(playlists[-1])
        self._refresh_playlist_list()
        self._add_pl_input.clear()
        self.statusMsg.setText("Playlist saved")
        # Optionally switch back to download view
        self._show_view("download")


# Main
if __name__ == "__main__":
    app = QApplication(sys.argv)
    Screen = MainWindow()
    Screen.setFixedHeight(600)
    Screen.setFixedWidth(1450)
    Screen.setWindowFlags(Qt.FramelessWindowHint)
    Screen.setAttribute(Qt.WA_TranslucentBackground)
    Screen.show()
    sys.exit(app.exec())
