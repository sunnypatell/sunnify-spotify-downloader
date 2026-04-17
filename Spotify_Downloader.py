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

__version__ = "2.1.0"

import concurrent.futures
import datetime as _dt
import json
import os
import re
import subprocess
import sys
import threading
import webbrowser

import requests
from mutagen.easyid3 import EasyID3
from mutagen.id3 import APIC, ID3
from PyQt5.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QRect,
    Qt,
    QThread,
    QTimer,
    pyqtSignal,
    pyqtSlot,
)
from PyQt5.QtGui import QCursor, QImage, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
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
    detect_spotify_url_type,
    extract_album_id,
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
# means bitrate is ignored by the ffmpeg postprocessor.
SUPPORTED_FORMATS = {
    "mp3": {"ext": "mp3", "lossy": True},
    "m4a": {"ext": "m4a", "lossy": True},
    "opus": {"ext": "opus", "lossy": True},
    "flac": {"ext": "flac", "lossy": False},
    "wav": {"ext": "wav", "lossy": False},
}
SUPPORTED_QUALITIES = ("128", "192", "256", "320")
FILENAME_TEMPLATES = {
    "{title} - {artists}": "Title - Artists",
    "{artists} - {title}": "Artists - Title",
    "{track_num:02d} {title} - {artists}": "01 Title - Artists (numbered)",
    "{track_num:02d} {artists} - {title}": "01 Artists - Title (numbered)",
}
DEFAULT_TEMPLATE = "{title} - {artists}"
MAX_RECENT_PLAYLISTS = 10


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


def load_config() -> dict:
    """Load user config. Missing/corrupt file returns sensible defaults."""
    defaults = {
        "version": 1,
        "download_path": None,
        "format": "mp3",
        "quality": "192",
        "filename_template": DEFAULT_TEMPLATE,
        "recent_playlists": [],
    }
    try:
        with open(_config_path(), encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return defaults
        defaults.update({k: v for k, v in data.items() if k in defaults})
        # Validate and clamp values
        if defaults["format"] not in SUPPORTED_FORMATS:
            defaults["format"] = "mp3"
        if defaults["quality"] not in SUPPORTED_QUALITIES:
            defaults["quality"] = "192"
        if defaults["filename_template"] not in FILENAME_TEMPLATES:
            defaults["filename_template"] = DEFAULT_TEMPLATE
        if not isinstance(defaults["recent_playlists"], list):
            defaults["recent_playlists"] = []
        return defaults
    except (OSError, json.JSONDecodeError):
        return defaults


def save_config(config: dict) -> None:
    """Persist user config. Silently swallows IO errors (best-effort)."""
    try:
        with open(_config_path(), "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
    except OSError as exc:
        print(f"[*] Could not save config: {exc}")


def open_folder_in_file_manager(path: str) -> None:
    """Open a folder in the platform's file manager (Finder, Explorer, xdg)."""
    if not path or not os.path.isdir(path):
        return
    try:
        if sys.platform == "darwin":
            subprocess.run(["open", path], check=False)
        elif sys.platform == "win32":
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            subprocess.run(["xdg-open", path], check=False)
    except OSError as exc:
        print(f"[*] Could not open folder: {exc}")


_SPOTIFY_URL_PATTERN = re.compile(
    r"(?:https?://open\.spotify\.com/(?:intl-[a-z]{2,}/)?(?:playlist|track|album)/[a-zA-Z0-9]+"
    r"|spotify:(?:playlist|track|album):[a-zA-Z0-9]+)"
)


def extract_spotify_url_from_text(text: str) -> str | None:
    """Find the first Spotify playlist/track/album URL or URI in a text blob.

    Used for clipboard auto-detect and drag-and-drop payload parsing.
    Accepts canonical URLs, /intl-xx/ locale URLs, and spotify: URIs.
    """
    if not text:
        return None
    match = _SPOTIFY_URL_PATTERN.search(text)
    return match.group(0) if match else None


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
        filename_template: str = DEFAULT_TEMPLATE,
    ):
        super().__init__()
        self.counter = 0  # Initialize counter to zero
        self.session = requests.Session()
        self.spotifydown_api = None
        self._cancel_event = cancel_event or threading.Event()
        self._failed_tracks: list[str] = []  # Track failed downloads
        self._counter_lock = threading.Lock()
        self._failed_lock = threading.Lock()
        self._filename_lock = threading.Lock()
        self._in_flight_files: set[str] = set()
        # Set to True during parallel playlist downloads so workers can suppress
        # per-track UI noise (label flicker, thumbnail spam, progress bar jitter)
        # that only makes sense for a single active download.
        self._parallel_mode = False
        self._total_tracks = 0
        # Output format options. audio_format must be a key of SUPPORTED_FORMATS;
        # quality only applies to lossy formats. filename_template accepts the
        # placeholders {title}, {artists}, {album}, and {track_num}.
        self.audio_format = audio_format if audio_format in SUPPORTED_FORMATS else "mp3"
        self.audio_quality = audio_quality if audio_quality in SUPPORTED_QUALITIES else "192"
        self.filename_template = filename_template or DEFAULT_TEMPLATE

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
        owner = metadata.owner or "Spotify"
        return f"{metadata.name} - {owner}".strip(" -")

    def prepare_playlist_folder(self, base_folder, playlist_name):
        if not os.path.exists(base_folder):
            os.makedirs(base_folder)
        safe_name = "".join(
            character
            for character in playlist_name
            if character.isalnum() or character in [" ", "_"]
        ).strip()
        if not safe_name:
            safe_name = "Sunnify Playlist"
        playlist_folder = os.path.join(base_folder, safe_name)
        os.makedirs(playlist_folder, exist_ok=True)
        return playlist_folder

    def _format_filename(self, track, track_num: int = 0) -> str:
        """Build a filename (without extension) from the user's template.

        Any unresolvable placeholder falls back to the default template so a
        malformed template never breaks a download. Track number is 1-based
        when {track_num} is present; 0 means "not set" but formatters still
        accept it.
        """
        parts = {
            "title": self.sanitize_text(track.title or ""),
            "artists": self.sanitize_text(track.artists or ""),
            "album": self.sanitize_text(track.album or ""),
            "track_num": track_num,
        }
        try:
            name = self.filename_template.format(**parts)
        except (KeyError, IndexError, ValueError):
            name = DEFAULT_TEMPLATE.format(**parts)
        name = name.strip()
        return name or "Unknown Track"

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

        # progress_hooks give us fine-grained cancel during yt-dlp downloads.
        # Raising here interrupts the current fragment and yt-dlp propagates
        # as a DownloadError which _download_one_track catches per-track.
        def _cancel_hook(_info):
            if self.is_cancelled():
                raise RuntimeError("Download cancelled by user")

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
            "progress_hooks": [_cancel_hook],
            "postprocessors": [postprocessor],
        }
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_query, download=True)
            if info.get("entries"):
                info = info["entries"][0]
            expected_path = base + "." + ext
            if os.path.exists(expected_path):
                return expected_path
            fallback = ydl.prepare_filename(info)
            if os.path.exists(fallback):
                return fallback
        return base + "." + ext

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

    def _download_one_track(
        self,
        track,
        playlist_folder_path,
        default_cover_url,
        track_num: int = 0,
        enrich_cover: bool = True,
    ):
        """Download a single track. Runs inside a ThreadPoolExecutor worker.

        Returns None on success, the track title on failure.

        In parallel mode (self._parallel_mode), per-track UI noise (song_meta
        preview, per-byte progress) is suppressed because those widgets are
        single-track and would flicker with N workers in flight. add_song_meta
        still fires so ID3 tags + cover art get written to every output file.

        When enrich_cover is True (playlist context), the worker hits
        /embed/track/{id} to get the real per-track cover. Playlist embed
        trackList does not include per-track covers so without this every
        track ends up with the playlist cover. Albums pass enrich_cover=False
        because every track legitimately shares the album cover.
        """
        if self.is_cancelled():
            return None

        track_title = track.title
        artists = track.artists

        # Filename from the user's template, with correct extension for format
        ext = SUPPORTED_FORMATS.get(self.audio_format, SUPPORTED_FORMATS["mp3"])["ext"]
        base_name = self._format_filename(track, track_num=track_num)
        filename = f"{base_name}.{ext}"
        filepath = os.path.join(playlist_folder_path, filename)

        # Filename collision guard: two different tracks can sanitize to the
        # same filename (e.g. "Café" vs "Cafe"). Under parallel downloads the
        # naive os.path.exists check has a TOCTOU race where both workers pass
        # the check and clobber each other's files. Claim the filename via a
        # lock; if taken, suffix with track id to de-dupe.
        with self._filename_lock:
            if filepath in self._in_flight_files:
                filepath = os.path.join(
                    playlist_folder_path,
                    f"{base_name} [{track.id}].{ext}",
                )
            self._in_flight_files.add(filepath)

        # Per-track cover + release_date enrichment. Playlist embed trackList
        # omits cover URLs and release dates entirely, so every track needs a
        # separate /embed/track/{id} fetch. Runs synchronously inside each
        # worker before the YouTube search, so it adds ~100-300ms per track
        # in sequential mode; in parallel mode that cost overlaps with
        # downloads happening in other workers.
        cover_url = track.cover_url
        release_date = track.release_date or ""
        if (
            enrich_cover
            and not cover_url
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
                pass  # Fall through to default

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

        # In sequential mode, emit song_meta at start so the UI shows what's
        # currently downloading. In parallel mode, skip it: the UI widgets
        # can only show one track at a time and flickering between N workers
        # is worse than a stable "now processing" message.
        if not self._parallel_mode:
            self.song_meta.emit(dict(song_meta))

        try:
            if os.path.exists(filepath):
                self.add_song_meta.emit(song_meta)
                self._finish_track_ui(ok=True)
                return None

            search_query = f"ytsearch1:{track_title} {artists} audio"
            try:
                final_path = self.download_track_audio(search_query, filepath)
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

    def _reset_state(self) -> None:
        """Reset mutable state between scrape invocations."""
        with self._counter_lock:
            self.counter = 0
        with self._failed_lock:
            self._failed_tracks.clear()
        with self._filename_lock:
            self._in_flight_files.clear()
        self._parallel_mode = False
        self._total_tracks = 0

    def _materialize_tracks(self, track_iter) -> list:
        """Consume a track generator into a list, checking cancel between
        yields so users can abort mid-fetch on very large playlists.
        """
        tracks: list = []
        for track in track_iter:
            if self.is_cancelled():
                break
            tracks.append(track)
        return tracks

    def _run_worker_pool(
        self, tracks: list, playlist_folder_path: str, cover_url: str | None, enrich_cover: bool
    ) -> None:
        """Download a list of tracks either sequentially or in parallel.

        Picks worker count based on len(tracks) and the MAX_WORKERS cap. Tiny
        playlists (<3) stay sequential so the single-track UI feels unchanged.
        """
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
                    track,
                    playlist_folder_path,
                    cover_url,
                    track_num=idx,
                    enrich_cover=enrich_cover,
                )
            return

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
                futures = [
                    executor.submit(
                        self._download_one_track,
                        track,
                        playlist_folder_path,
                        cover_url,
                        idx,
                        enrich_cover,
                    )
                    for idx, track in enumerate(tracks, start=1)
                ]
                for future in concurrent.futures.as_completed(futures):
                    if self.is_cancelled():
                        # Cancel remaining futures that haven't started yet.
                        # In-flight downloads check is_cancelled at their own
                        # top and return early; yt-dlp progress_hooks cancel
                        # catches the fragment-level window too.
                        for f in futures:
                            f.cancel()
                        break
                    try:
                        future.result()
                    except Exception as exc:
                        msg = f"Unexpected worker error: {exc}"
                        print(f"[*] {msg}")
                        self.error_signal.emit(msg)
        finally:
            # Reset parallel_mode only after the executor has fully shut down
            # (context manager exit waits on in-flight workers). If we reset
            # inside the `with`, workers still running after a break would
            # observe False and emit single-track UI signals.
            self._parallel_mode = False

    def scrape_playlist(self, spotify_playlist_link, music_folder):
        self._reset_state()

        playlist_id = self.returnSPOT_ID(spotify_playlist_link)
        self.PlaylistID.emit(playlist_id)

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

        # Materialize the generator on the main scraper thread (generators are
        # not thread-safe in python). Cancel is checked per yield so large
        # playlists can abort mid-fetch without waiting through the full
        # spclient + per-track metadata window.
        tracks = self._materialize_tracks(spotify_api.iter_playlist_tracks(playlist_id))
        self._total_tracks = len(tracks)

        if self.is_cancelled():
            self.PlaylistCompleted.emit("Download cancelled")
            return

        self.Resetprogress_signal.emit(0)

        # Playlists: enrich per-track covers because embed trackList does not
        # include them (all tracks would otherwise share the playlist cover).
        self._run_worker_pool(tracks, playlist_folder_path, metadata.cover_url, enrich_cover=True)

        if self.is_cancelled():
            self.PlaylistCompleted.emit("Download cancelled")
            return

        if self._failed_tracks:
            self.PlaylistCompleted.emit(f"Done! {len(self._failed_tracks)} track(s) failed")
        else:
            self.PlaylistCompleted.emit("Download Complete!")

    def scrape_album(self, spotify_album_link, music_folder):
        """Download every track from a Spotify album.

        Treats albums identically to playlists from the caller's perspective,
        but uses /embed/album/{id} (not /embed/playlist/{id}) and disables
        per-track cover enrichment since every album track legitimately
        shares the album cover (which iter_album_tracks already sets).
        """
        self._reset_state()

        album_id = extract_album_id(spotify_album_link)
        self.PlaylistID.emit(album_id)

        if self.is_cancelled():
            self.PlaylistCompleted.emit("Download cancelled")
            return

        try:
            spotify_api = self.ensure_spotifydown_api()
        except SpotifyDownAPIError as exc:
            raise RuntimeError(str(exc)) from exc

        metadata = spotify_api.get_album_metadata(album_id)
        display_name = self.format_playlist_name(metadata)
        self.song_Album.emit(display_name)

        album_folder_path = self.prepare_playlist_folder(music_folder, display_name)

        tracks = self._materialize_tracks(spotify_api.iter_album_tracks(album_id))
        self._total_tracks = len(tracks)

        if self.is_cancelled():
            self.PlaylistCompleted.emit("Download cancelled")
            return

        self.Resetprogress_signal.emit(0)
        self._run_worker_pool(tracks, album_folder_path, metadata.cover_url, enrich_cover=False)

        if self.is_cancelled():
            self.PlaylistCompleted.emit("Download cancelled")
            return

        if self._failed_tracks:
            self.PlaylistCompleted.emit(f"Done! {len(self._failed_tracks)} track(s) failed")
        else:
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
        self.song_Album.emit("Single Track Download")

        if not os.path.exists(music_folder):
            os.makedirs(music_folder)

        self.Resetprogress_signal.emit(0)

        track_title = track.title
        artists = track.artists
        ext = SUPPORTED_FORMATS.get(self.audio_format, SUPPORTED_FORMATS["mp3"])["ext"]
        filename = f"{self._format_filename(track, track_num=1)}.{ext}"
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
        try:
            final_path = self.download_track_audio(search_query, filepath)
        except Exception as error_status:
            error_msg = self._get_user_friendly_error(error_status, track_title)
            print(f"[*] Error downloading '{track_title}': {error_status}")
            self.PlaylistCompleted.emit(error_msg)
            return

        if not final_path or not os.path.exists(final_path):
            print(f"[*] Download did not produce an audio file for: {track_title}")
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
        filename_template: str = DEFAULT_TEMPLATE,
    ):
        super().__init__()
        self.spotify_link = spotify_link
        self.music_folder = music_folder or os.path.join(os.getcwd(), "music")
        self._cancel_event = cancel_event or threading.Event()
        self.scraper = MusicScraper(
            cancel_event=self._cancel_event,
            audio_format=audio_format,
            audio_quality=audio_quality,
            filename_template=filename_template,
        )

    def request_cancel(self):
        """Request cancellation of the download."""
        self._cancel_event.set()

    def run(self):
        self.progress_update.emit("Scraping started...")
        try:
            url_type, _ = detect_spotify_url_type(self.spotify_link)
            if url_type == "track":
                self.scraper.scrape_track(self.spotify_link, self.music_folder)
            elif url_type == "album":
                self.scraper.scrape_album(self.spotify_link, self.music_folder)
            else:
                self.scraper.scrape_playlist(self.spotify_link, self.music_folder)
            self.progress_update.emit("Scraping completed.")
        except Exception as e:
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
        print(f"[*] Error fetching cover: {exc}")
    return None


def _write_metadata_mp3(filename: str, tags: dict, cover_bytes: bytes | None) -> None:
    """Write ID3 tags + embedded cover art to an MP3."""
    audio = EasyID3(filename)
    audio["title"] = tags.get("title", "")
    audio["artist"] = tags.get("artists", "")
    audio["album"] = tags.get("album", "")
    audio["date"] = tags.get("releaseDate", "")
    track_num = tags.get("trackNumber") or 0
    if track_num:
        audio["tracknumber"] = str(track_num)
    audio.save()
    if cover_bytes:
        id3 = ID3(filename)
        id3["APIC"] = APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=cover_bytes)
        id3.save()


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
        """Write tags + cover art synchronously.

        Dispatches on file extension because each container format uses a
        different tag system (ID3 for mp3, iTunes atoms for m4a, Vorbis
        comments for flac). Opus/WAV are skipped with a log since container
        tagging is either limited or not worth the extra dependency surface
        for this app's educational scope.
        """
        try:
            ext = os.path.splitext(self.filename)[1].lower()
            writer = _METADATA_WRITERS.get(ext)
            if writer is None:
                print(f"[*] Skipping metadata: no writer for {ext}")
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
    """Modal settings dialog covering folder, format, quality, and template.

    Keeps the purple translucent vibe (frameless, rounded) by mirroring the
    parent window's WA_TranslucentBackground flag when available.
    """

    def __init__(self, parent, config: dict):
        super().__init__(parent)
        self.setWindowTitle("Sunnify Settings")
        self.setModal(True)
        self.setMinimumWidth(440)
        self._config = dict(config)

        self._folder_label = QLabel(self._config.get("download_path") or "(not set)")
        self._folder_label.setWordWrap(True)
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
        quality = self._config.get("quality", "192")
        self._quality_cb.setCurrentText(f"{quality} kbps")
        self._on_format_change(self._format_cb.currentText())

        self._template_cb = QComboBox()
        for tmpl, label in FILENAME_TEMPLATES.items():
            self._template_cb.addItem(label, userData=tmpl)
        current_template = self._config.get("filename_template", DEFAULT_TEMPLATE)
        for i in range(self._template_cb.count()):
            if self._template_cb.itemData(i) == current_template:
                self._template_cb.setCurrentIndex(i)
                break

        diagnostics_btn = QPushButton("Run API diagnostics")
        diagnostics_btn.clicked.connect(self._run_diagnostics)

        form = QFormLayout()
        form.addRow("Download folder:", folder_row)
        form.addRow("Audio format:", self._format_cb)
        form.addRow("Audio quality:", self._quality_cb)
        form.addRow("Filename template:", self._template_cb)
        form.addRow("", diagnostics_btn)

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
            chosen = (
                os.path.join(folder, "Sunnify") if os.path.basename(folder) != "Sunnify" else folder
            )
            self._folder_label.setText(chosen)

    def _on_format_change(self, fmt: str) -> None:
        """Lossy formats get a quality selector; lossless formats ignore it."""
        is_lossy = SUPPORTED_FORMATS.get(fmt, {}).get("lossy", True)
        self._quality_cb.setEnabled(is_lossy)

    def _run_diagnostics(self) -> None:
        """Lightweight check: validate a known-good playlist + YouTube search."""
        self.setCursor(QCursor(Qt.WaitCursor))
        try:
            client = PlaylistClient()
            ok = client.validate_playlist("37i9dQZF1DXcBWIGoYBM5M")
            from yt_dlp import YoutubeDL

            yt_ok = False
            try:
                with YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True}) as ydl:
                    info = ydl.extract_info("ytsearch1:test", download=False)
                    yt_ok = bool(info.get("entries"))
            except Exception:
                yt_ok = False

            msg = (
                f"Spotify embed: {'OK' if ok else 'FAIL'}\n"
                f"YouTube search: {'OK' if yt_ok else 'FAIL'}"
            )
            QMessageBox.information(self, "API Diagnostics", msg)
        finally:
            self.setCursor(QCursor(Qt.ArrowCursor))

    def result_config(self) -> dict:
        """Return the updated config dict after accept()."""
        self._config["download_path"] = self._folder_label.text()
        self._config["format"] = self._format_cb.currentText()
        self._config["quality"] = self._quality_cb.currentText().split()[0]
        idx = self._template_cb.currentIndex()
        tmpl = self._template_cb.itemData(idx) if idx >= 0 else DEFAULT_TEMPLATE
        self._config["filename_template"] = tmpl or DEFAULT_TEMPLATE
        return self._config


def _ytdlp_version_is_stale(max_age_days: int = 60) -> tuple[bool, str]:
    """Return (is_stale, version_string). YT-DLP releases on YYYY.M.D format.

    Staleness is measured against today. Used to surface a startup warning
    because production users started hitting 403s when YouTube changed
    anti-bot measures and their bundled yt-dlp was more than two months old.
    """
    try:
        import yt_dlp.version as _v  # type: ignore[import-not-found]

        ver = _v.__version__
    except Exception:
        return (False, "unknown")
    try:
        parts = ver.split(".")
        release = _dt.date(int(parts[0]), int(parts[1]), int(parts[2]))
        age = (_dt.date.today() - release).days
        return (age > max_age_days, ver)
    except (ValueError, IndexError):
        return (False, ver)


# Main Window
class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        """MainWindow constructor"""
        super().__init__()
        self.setupUi(self)

        # Load persisted config so settings survive restarts
        self._config = load_config()
        self.download_path = self._config.get("download_path") or self._get_default_download_path()
        self._download_path_set = bool(self._config.get("download_path"))
        self._active_threads = []  # Keep references to running threads to prevent GC crashes
        self._is_downloading = False  # Track download state for stop button
        self._cancel_event = threading.Event()  # Event for cooperative thread cancellation
        self._last_download_folder: str | None = None
        self._clipboard_offered: set[str] = set()

        self.SONGINFORMATION.setGraphicsEffect(
            QGraphicsDropShadowEffect(blurRadius=25, xOffset=2, yOffset=2)
        )
        self.PlaylistLink.returnPressed.connect(self.on_returnButton)
        self.DownloadBtn.clicked.connect(self.on_returnButton)

        self.showPreviewCheck.stateChanged.connect(self.show_preview)

        self.Closed.clicked.connect(self.exitprogram)
        self.Select_Home.clicked.connect(self.Linkedin)
        self.SettingsBtn.clicked.connect(self.open_settings)

        # Drag-and-drop of a Spotify URL onto the window auto-fills the input
        self.setAcceptDrops(True)

        # Keyboard shortcuts
        from PyQt5.QtGui import QKeySequence
        from PyQt5.QtWidgets import QShortcut

        QShortcut(QKeySequence("Ctrl+,"), self, self.open_settings)
        QShortcut(QKeySequence("Meta+,"), self, self.open_settings)
        QShortcut(QKeySequence("Escape"), self, self._escape_pressed)
        QShortcut(QKeySequence("Ctrl+Shift+A"), self, self.show_about)
        QShortcut(QKeySequence("Meta+Shift+A"), self, self.show_about)
        QShortcut(QKeySequence("Ctrl+Q"), self, self.exitprogram)
        QShortcut(QKeySequence("Meta+Q"), self, self.exitprogram)

        stale, ver = _ytdlp_version_is_stale()
        if stale:
            self.statusMsg.setText(f"yt-dlp {ver} is stale; run: pip install -U yt-dlp")
        else:
            self.statusMsg.setText("Ready to download")

        # Look for a Spotify URL in the clipboard right away
        self._maybe_paste_clipboard_url()

    def _escape_pressed(self) -> None:
        """Esc stops an active download. Ignored when idle."""
        if self._is_downloading:
            self._stop_download()

    def show_about(self) -> None:
        """Open the About dialog (Cmd+Shift+A)."""
        AboutDialog(self).exec_()

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
            # Create Sunnify subfolder so downloads don't splatter everywhere
            self.download_path = os.path.join(folder, "Sunnify")
            self._download_path_set = True
            self._config["download_path"] = self.download_path
            save_config(self._config)
            return True
        return False

    def open_settings(self):
        """Open settings dialog covering folder + format/quality/template."""
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
                    "filename_template": new.get("filename_template", DEFAULT_TEMPLATE),
                }
            )
            save_config(self._config)
            self.statusMsg.setText("Settings saved")

    def _maybe_paste_clipboard_url(self) -> None:
        """If the clipboard holds a Spotify URL we haven't offered yet, and
        the input field is empty, auto-fill it. Keeps a tiny "seen" set so
        we don't repeatedly re-paste the same URL when the user switches
        focus in and out of the window.
        """
        clip = QApplication.clipboard()
        text = clip.text() if clip else ""
        url = extract_spotify_url_from_text(text)
        if not url or url in self._clipboard_offered:
            return
        if self.PlaylistLink.text().strip():
            return
        self.PlaylistLink.setText(url)
        self._clipboard_offered.add(url)
        self.statusMsg.setText("Pasted Spotify URL from clipboard")

    def changeEvent(self, event):
        """Re-check clipboard when window regains focus."""
        try:
            from PyQt5.QtCore import QEvent

            if event.type() == QEvent.ActivationChange and self.isActiveWindow():
                self._maybe_paste_clipboard_url()
        except Exception:
            pass
        super().changeEvent(event)

    def dragEnterEvent(self, event):
        """Accept drags that look like text or URLs (check payload lazily)."""
        mime = event.mimeData()
        if mime.hasText() or mime.hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        """Accept a Spotify URL dropped onto the window."""
        mime = event.mimeData()
        # Try direct URLs first (typically browser drags)
        for qurl in mime.urls() if mime.hasUrls() else []:
            candidate = qurl.toString()
            match = extract_spotify_url_from_text(candidate)
            if match:
                self.PlaylistLink.setText(match)
                self.statusMsg.setText("Received Spotify URL via drag and drop")
                event.acceptProposedAction()
                return
        # Fall back to scanning plain text payload
        match = extract_spotify_url_from_text(mime.text() if mime.hasText() else "")
        if match:
            self.PlaylistLink.setText(match)
            self.statusMsg.setText("Received Spotify URL via drag and drop")
            event.acceptProposedAction()
        else:
            event.ignore()

    def _record_recent_download(self, url: str, name: str | None, track_count: int) -> None:
        """Append a completed download to the persisted recent list."""
        entry = {
            "url": url,
            "name": name or "Unknown",
            "track_count": track_count,
            "downloaded_at": _dt.datetime.now().isoformat(timespec="seconds"),
        }
        recents = [r for r in self._config.get("recent_playlists", []) if r.get("url") != url]
        recents.insert(0, entry)
        self._config["recent_playlists"] = recents[:MAX_RECENT_PLAYLISTS]
        save_config(self._config)

    def _offer_reveal_folder(self, folder: str) -> None:
        """Show the completion summary. Lets the user open the folder or retry
        any tracks that failed.
        """
        if not folder or not os.path.isdir(folder):
            return
        total = self._current_download_total or 0
        failed = list(self._current_failed_tracks or [])
        dialog = CompletionDialog(self, folder, total, failed)
        dialog.exec_()
        if dialog.retry_clicked and failed:
            self._retry_failed_tracks(failed)

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
            # Validate URL type (now covers track/playlist/album)
            url_type, _ = detect_spotify_url_type(spotify_url)
            self.statusMsg.setText(f"Detected: {url_type}")

            # Reset cancel event and set downloading state
            self._cancel_event = threading.Event()
            self._is_downloading = True
            self.DownloadBtn.setText("Stop")
            self._current_download_url = spotify_url
            self._current_download_name: str | None = None
            self._current_download_succeeded = False
            self._current_download_total = 0
            self._current_failed_tracks: list[str] = []

            self.scraper_thread = ScraperThread(
                spotify_url,
                self.download_path,
                cancel_event=self._cancel_event,
                audio_format=self._config.get("format", "mp3"),
                audio_quality=self._config.get("quality", "192"),
                filename_template=self._config.get("filename_template", DEFAULT_TEMPLATE),
            )
            self.scraper_thread.progress_update.connect(self.update_progress)
            self.scraper_thread.finished.connect(self.thread_finished)
            self.scraper_thread.scraper.song_Album.connect(self.update_AlbumName)
            self.scraper_thread.scraper.song_Album.connect(self._capture_playlist_name)
            self.scraper_thread.scraper.song_meta.connect(self.update_song_META)
            self.scraper_thread.scraper.add_song_meta.connect(self.add_song_META)
            self.scraper_thread.scraper.dlprogress_signal.connect(self.update_song_progress)
            self.scraper_thread.scraper.Resetprogress_signal.connect(self.Reset_song_progress)
            self.scraper_thread.scraper.PlaylistCompleted.connect(self._on_playlist_complete)
            self.scraper_thread.scraper.error_signal.connect(lambda x: self.statusMsg.setText(x))

            # Connect the count_updated signal to the update_counter slot
            self.scraper_thread.scraper.count_updated.connect(self.update_counter)

            self.scraper_thread.start()

        except ValueError as e:
            self.statusMsg.setText(str(e))
            self._is_downloading = False
            self.DownloadBtn.setText("Download")

    @pyqtSlot(str)
    def _capture_playlist_name(self, name: str) -> None:
        """Remember the resolved playlist/album name for recent-downloads."""
        self._current_download_name = name

    @pyqtSlot(str)
    def _on_playlist_complete(self, message: str) -> None:
        """Status message + track completion for history/reveal-folder."""
        self.statusMsg.setText(message)
        completed = message.startswith("Download Complete") or message.startswith("Done!")
        self._current_download_succeeded = completed
        if completed:
            folder = None
            if self._current_download_name:
                safe = (
                    "".join(
                        c for c in self._current_download_name if c.isalnum() or c in [" ", "_"]
                    ).strip()
                    or "Sunnify Playlist"
                )
                folder = os.path.join(self.download_path, safe)
            self._last_download_folder = folder
            try:
                track_count = int(self.CounterLabel.text().split()[-1])
            except (ValueError, IndexError):
                track_count = 0
            # Snapshot the scraper's counters for the completion dialog
            if hasattr(self, "scraper_thread") and self.scraper_thread is not None:
                try:
                    self._current_download_total = self.scraper_thread.scraper._total_tracks
                    self._current_failed_tracks = list(self.scraper_thread.scraper._failed_tracks)
                except AttributeError:
                    self._current_download_total = track_count
                    self._current_failed_tracks = []
            if hasattr(self, "_current_download_url"):
                self._record_recent_download(
                    self._current_download_url,
                    self._current_download_name,
                    track_count,
                )

    def _retry_failed_tracks(self, failed_titles: list[str]) -> None:
        """Kick off a fresh download restricted to the tracks that failed.

        The simplest effective retry is to rerun the same URL; any tracks
        whose files are already on disk will be skipped by the existing
        os.path.exists guard, so only the failed set does real work.
        """
        if not hasattr(self, "_current_download_url") or self._is_downloading:
            return
        self.PlaylistLink.setText(self._current_download_url)
        self.statusMsg.setText(f"Retrying {len(failed_titles)} failed track(s)...")
        self.on_returnButton()

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

        # Offer reveal-in-finder on successful completion.
        if self._current_download_succeeded and self._last_download_folder:
            self._offer_reveal_folder(self._last_download_folder)

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
            self.ArtistNameText.setText(song_meta.get("artists", ""))
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
        self._preview_animation = QPropertyAnimation(self.SONGINFORMATION, b"geometry")
        start_rect = self.SONGINFORMATION.geometry()
        self._preview_animation.setDuration(220)
        self._preview_animation.setStartValue(start_rect)
        self._preview_animation.setEndValue(
            QRect(start_rect.x(), start_rect.y(), 0, start_rect.height())
        )
        self._preview_animation.setEasingCurve(QEasingCurve.InOutQuad)
        self._preview_animation.finished.connect(lambda: self.SONGINFORMATION.setVisible(False))
        self._preview_animation.start()

    def OpenSongInformation(self):
        # Anchor the panel to the right edge of the window and match the card
        # height so it feels attached rather than floating.
        panel_width = 280
        panel_height = max(self.height() - 48, 360)
        y_offset = 24
        x_start = self.width()
        x_end = self.width() - panel_width - 16

        self.SONGINFORMATION.setVisible(True)
        self.SONGINFORMATION.setGeometry(x_start, y_offset, 0, panel_height)

        self._preview_animation = QPropertyAnimation(self.SONGINFORMATION, b"geometry")
        self._preview_animation.setDuration(320)
        self._preview_animation.setEndValue(QRect(x_end, y_offset, panel_width, panel_height))
        self._preview_animation.setEasingCurve(QEasingCurve.OutCubic)
        self._preview_animation.start()

    def show_preview(self, state):
        if state == 2:  # Qt.Checked
            self.OpenSongInformation()
        else:
            self.CloseSongInformation()

    def resizeEvent(self, event):
        """Keep the sliding preview panel anchored to the window's right edge."""
        super().resizeEvent(event)
        if self.SONGINFORMATION.isVisible() and self.SONGINFORMATION.width() > 0:
            panel_width = self.SONGINFORMATION.width()
            panel_height = max(self.height() - 48, 360)
            self.SONGINFORMATION.setGeometry(
                self.width() - panel_width - 16, 24, panel_width, panel_height
            )

    def exitprogram(self):
        sys.exit()

    def Linkedin(self):
        webbrowser.open("https://www.linkedin.com/in/sunny-patel-30b460204/")


# ---------------------------------------------------------------------------
# Splash screen. Brief branded intro instead of a cold window appear.
# ---------------------------------------------------------------------------
class SplashScreen(QDialog):
    """A brief, branded splash shown on launch for ~1.5s."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(380, 220)

        from theme import Color as _C
        from theme import Font as _F

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)

        card = QLabel(self)
        card.setStyleSheet(
            f"background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,"
            f" stop:0 {_C.gradient_top}, stop:1 {_C.gradient_bot});"
            f" border-radius: 16px; border: 1px solid {_C.border};"
        )
        card.setGraphicsEffect(QGraphicsDropShadowEffect(blurRadius=40, xOffset=0, yOffset=10))
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(6)

        title = QLabel("Sunnify", card)
        title.setStyleSheet(
            f"color: {_C.fg_primary}; font-size: 28px; font-weight: 800; letter-spacing: 0.5px;"
        )
        title.setAlignment(Qt.AlignCenter)

        tagline = QLabel("Spotify playlists, tracks & albums to local MP3s.", card)
        tagline.setStyleSheet(f"color: {_C.fg_secondary}; font-size: {_F.small}px;")
        tagline.setAlignment(Qt.AlignCenter)

        version = QLabel(f"Version {__version__}", card)
        version.setStyleSheet(f"color: {_C.fg_muted}; font-size: {_F.caption}px;")
        version.setAlignment(Qt.AlignCenter)

        card_layout.addStretch(1)
        card_layout.addWidget(title)
        card_layout.addWidget(tagline)
        card_layout.addSpacing(8)
        card_layout.addWidget(version)
        card_layout.addStretch(1)

        outer.addWidget(card)

    def show_and_close(self, on_done) -> None:
        """Show the splash for the duration defined in theme.Motion.splash."""
        from theme import Motion as _M

        self.show()
        QTimer.singleShot(_M.splash, lambda: (self.close(), on_done()))


# ---------------------------------------------------------------------------
# About dialog. Version, author, license, project links.
# ---------------------------------------------------------------------------
class AboutDialog(QDialog):
    """A small, branded About dialog shown via Cmd+Shift+A or the settings menu."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About Sunnify")
        self.setModal(True)
        self.setMinimumWidth(380)

        from theme import Color as _C
        from theme import Font as _F

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title = QLabel("Sunnify", self)
        title.setStyleSheet(f"color: {_C.fg_primary}; font-size: 24px; font-weight: 800;")
        layout.addWidget(title)

        tagline = QLabel("Download Spotify playlists, tracks, and albums as tagged MP3s.", self)
        tagline.setStyleSheet(f"color: {_C.fg_secondary}; font-size: {_F.body}px;")
        tagline.setWordWrap(True)
        layout.addWidget(tagline)

        facts = QLabel(
            f"Version {__version__}\n"
            "MIT licensed, educational project\n"
            "Built by Sunny Jayendra Patel",
            self,
        )
        facts.setStyleSheet(f"color: {_C.fg_muted}; font-size: {_F.small}px;")
        layout.addWidget(facts)

        btn_row = QHBoxLayout()
        homepage = QPushButton("Homepage", self)
        homepage.clicked.connect(
            lambda: webbrowser.open("https://github.com/sunnypatell/sunnify-spotify-downloader")
        )
        issues = QPushButton("Report an issue", self)
        issues.clicked.connect(
            lambda: webbrowser.open(
                "https://github.com/sunnypatell/sunnify-spotify-downloader/issues/new/choose"
            )
        )
        close = QPushButton("Close", self)
        close.clicked.connect(self.accept)

        btn_row.addWidget(homepage)
        btn_row.addWidget(issues)
        btn_row.addStretch(1)
        btn_row.addWidget(close)
        layout.addLayout(btn_row)


# ---------------------------------------------------------------------------
# Completion summary dialog. Shown after a playlist/album download finishes.
# Offers: open the folder, retry failed tracks, view all covered tracks.
# ---------------------------------------------------------------------------
class CompletionDialog(QDialog):
    """Summary dialog shown when a playlist or album finishes downloading."""

    def __init__(self, parent, folder: str, total: int, failed: list[str]):
        super().__init__(parent)
        self.setWindowTitle("Download Complete")
        self.setModal(True)
        self.setMinimumWidth(420)

        from theme import Color as _C
        from theme import Font as _F

        self._folder = folder
        self._failed = failed
        self.retry_clicked = False

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        headline = "Download complete" if not failed else "Download finished with errors"
        emoji = "✓" if not failed else "⚠"
        title = QLabel(f"{emoji}  {headline}", self)
        title.setStyleSheet(f"color: {_C.fg_primary}; font-size: 20px; font-weight: 700;")
        layout.addWidget(title)

        ok_count = max(total - len(failed), 0)
        summary = QLabel(f"{ok_count} of {total} track(s) downloaded to:\n{folder}", self)
        summary.setStyleSheet(f"color: {_C.fg_secondary}; font-size: {_F.body}px;")
        summary.setWordWrap(True)
        layout.addWidget(summary)

        if failed:
            failed_header = QLabel(f"{len(failed)} track(s) failed to download:", self)
            failed_header.setStyleSheet(
                f"color: {_C.warning}; font-size: {_F.small}px; font-weight: 700;"
            )
            layout.addWidget(failed_header)

            preview = "\n".join(f"  - {name}" for name in failed[:6])
            if len(failed) > 6:
                preview += f"\n  +{len(failed) - 6} more..."
            failed_list = QLabel(preview, self)
            failed_list.setStyleSheet(
                f"color: {_C.fg_muted}; font-size: {_F.small}px; font-family: {_F.mono_family};"
            )
            layout.addWidget(failed_list)

        btn_row = QHBoxLayout()
        open_btn = QPushButton("Open folder", self)
        open_btn.clicked.connect(lambda: open_folder_in_file_manager(self._folder))

        if failed:
            retry_btn = QPushButton(f"Retry {len(failed)} failed", self)
            retry_btn.clicked.connect(self._retry)
            btn_row.addWidget(retry_btn)

        done_btn = QPushButton("Done", self)
        done_btn.clicked.connect(self.accept)

        btn_row.addWidget(open_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(done_btn)
        layout.addLayout(btn_row)

    def _retry(self):
        self.retry_clicked = True
        self.accept()


# ---------------------------------------------------------------------------
# Friendly error dialog with a "Copy details" action and a link to open an issue.
# ---------------------------------------------------------------------------
class FriendlyErrorDialog(QDialog):
    """Error dialog with readable summary and copyable diagnostic details."""

    def __init__(self, parent, title: str, summary: str, details: str = ""):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(440)

        from theme import Color as _C
        from theme import Font as _F

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        headline = QLabel(f"⚠  {title}", self)
        headline.setStyleSheet(f"color: {_C.fg_primary}; font-size: 18px; font-weight: 700;")
        layout.addWidget(headline)

        msg = QLabel(summary, self)
        msg.setStyleSheet(f"color: {_C.fg_secondary}; font-size: {_F.body}px;")
        msg.setWordWrap(True)
        layout.addWidget(msg)

        if details:
            details_label = QLabel(details, self)
            details_label.setStyleSheet(
                f"color: {_C.fg_muted}; font-size: {_F.small}px;"
                f" font-family: {_F.mono_family};"
                f" background-color: {_C.bg_input}; padding: 8px; border-radius: 6px;"
            )
            details_label.setWordWrap(True)
            details_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            layout.addWidget(details_label)

        btn_row = QHBoxLayout()
        if details:
            copy_btn = QPushButton("Copy details", self)
            copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(details))
            btn_row.addWidget(copy_btn)
        issue_btn = QPushButton("Report", self)
        issue_btn.clicked.connect(
            lambda: webbrowser.open(
                "https://github.com/sunnypatell/sunnify-spotify-downloader/issues/new/choose"
            )
        )
        dismiss_btn = QPushButton("Dismiss", self)
        dismiss_btn.clicked.connect(self.accept)

        btn_row.addWidget(issue_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(dismiss_btn)
        layout.addLayout(btn_row)


# Main
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Sunnify")
    app.setApplicationDisplayName("Sunnify")
    app.setOrganizationName("Sunny Jayendra Patel")

    def _launch_main():
        screen = MainWindow()
        screen.setWindowFlags(Qt.FramelessWindowHint)
        screen.setAttribute(Qt.WA_TranslucentBackground)
        screen.show()
        # Keep reference on app to prevent GC
        app._sunnify_main = screen  # noqa: SLF001

    splash = SplashScreen()
    splash.show_and_close(_launch_main)

    sys.exit(app.exec())
