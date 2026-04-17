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

import concurrent.futures
import os
import sys
import threading
import webbrowser

import requests
from mutagen.easyid3 import EasyID3
from mutagen.id3 import APIC, ID3
from PyQt5.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QSize,
    Qt,
    QThread,
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


def load_config() -> dict:
    """Load persisted user config. Missing or corrupt file returns defaults."""
    import json

    defaults = {
        "version": 1,
        "download_path": None,
        "format": "mp3",
        "quality": "192",
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
        filename = f"{sanitized_title} - {sanitized_artists}.mp3"
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
                    f"{sanitized_title} - {sanitized_artists} [{track.id}].mp3",
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
        sanitized_title = self.sanitize_text(track_title)
        sanitized_artists = self.sanitize_text(artists)
        filename = f"{sanitized_title} - {sanitized_artists}.mp3"
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
    ):
        super().__init__()
        self.spotify_link = spotify_link
        self.music_folder = music_folder or os.path.join(os.getcwd(), "music")
        self._cancel_event = cancel_event or threading.Event()
        self.scraper = MusicScraper(
            cancel_event=self._cancel_event,
            audio_format=audio_format,
            audio_quality=audio_quality,
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

        from PyQt5.QtWidgets import QLineEdit

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

        form = QFormLayout()
        form.addRow("Download folder:", folder_row)
        form.addRow("Audio format:", self._format_cb)
        form.addRow("Audio quality:", self._quality_cb)

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

    def result_config(self) -> dict:
        self._config["download_path"] = self._folder_label.text()
        self._config["format"] = self._format_cb.currentText()
        self._config["quality"] = self._quality_cb.currentText().split()[0]
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


# Main
if __name__ == "__main__":
    app = QApplication(sys.argv)
    Screen = MainWindow()
    Screen.setFixedHeight(500)
    Screen.setFixedWidth(750)
    Screen.setWindowFlags(Qt.FramelessWindowHint)
    Screen.setAttribute(Qt.WA_TranslucentBackground)
    Screen.show()
    sys.exit(app.exec())
