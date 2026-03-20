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
"""

__version__ = "2.0.2"

import json
import logging
import os
import sys
import threading
import webbrowser

# Silenciar warnings de yt_dlp
logging.getLogger("yt_dlp").setLevel(logging.ERROR)

import requests
from mutagen.easyid3 import EasyID3
from mutagen.id3 import APIC, ID3
from PyQt5.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QSize,
    Qt,
    QThread,
    QTimer,
    pyqtSignal,
    pyqtSlot,
)
from PyQt5.QtGui import QCursor, QImage, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QFileDialog,
    QGraphicsDropShadowEffect,
    QMainWindow,
    QMessageBox,
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

# ─────────────────────────────────────────────────────────────────────────────
# Persistencia de configuración en disco (JSON simple, sin dependencias extra)
# Guarda en: %APPDATA%\Sunnify\config.json  (Windows)
#            ~/.config/Sunnify/config.json  (Linux/macOS)
# ─────────────────────────────────────────────────────────────────────────────
def _get_config_path() -> str:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.environ.get("XDG_CONFIG_HOME", os.path.join(os.path.expanduser("~"), ".config"))
    config_dir = os.path.join(base, "Sunnify")
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, "config.json")


def load_config() -> dict:
    path = _get_config_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_config(data: dict) -> None:
    path = _get_config_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass  # No critical if save fails


# ─────────────────────────────────────────────────────────────────────────────

def get_ffmpeg_path():
    if getattr(sys, "frozen", False):
        base_path = sys._MEIPASS
        ffmpeg = os.path.join(base_path, "ffmpeg", "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
        if os.path.exists(ffmpeg):
            return os.path.join(base_path, "ffmpeg")

    ffmpeg_name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    for path in ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"]:
        if os.path.exists(os.path.join(path, ffmpeg_name)):
            return path

    import shutil
    found = shutil.which("ffmpeg")
    if found:
        return os.path.dirname(found)
    return None


class MusicScraper(QThread):
    PlaylistCompleted = pyqtSignal(str)
    PlaylistID = pyqtSignal(str)
    song_Album = pyqtSignal(str)
    song_meta = pyqtSignal(dict)
    add_song_meta = pyqtSignal(dict)
    count_updated = pyqtSignal(int, int)   # (descargadas, total)   ← CAMBIO
    dlprogress_signal = pyqtSignal(int)
    Resetprogress_signal = pyqtSignal(int)
    error_signal = pyqtSignal(str)

    def __init__(self, cancel_event: threading.Event | None = None):
        super().__init__()
        self.counter = 0
        self.session = requests.Session()
        self.spotifydown_api = None
        self._cancel_event = cancel_event or threading.Event()
        self._failed_tracks: list[str] = []

    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def _get_user_friendly_error(self, error: Exception, track_title: str = "") -> str:
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
        return sanitize_filename(text, allow_spaces=True)

    def format_playlist_name(self, metadata: PlaylistInfo):
        owner = metadata.owner or "Spotify"
        return f"{metadata.name} - {owner}".strip(" -")

    def prepare_playlist_folder(self, base_folder, playlist_name):
        os.makedirs(base_folder, exist_ok=True)
        safe_name = "".join(
            c for c in playlist_name if c.isalnum() or c in [" ", "_"]
        ).strip() or "Sunnify Playlist"
        playlist_folder = os.path.join(base_folder, safe_name)
        os.makedirs(playlist_folder, exist_ok=True)
        return playlist_folder

    def download_track_audio(self, search_query, destination):
        ffmpeg_path = get_ffmpeg_path()
        if not ffmpeg_path:
            raise RuntimeError("FFmpeg not found!")

        base, _ = os.path.splitext(destination)
        ydl_opts = {
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "outtmpl": base + ".%(ext)s",
            "ffmpeg_location": ffmpeg_path,
            "socket_timeout": 15,
            "retries": 2,
            "fragment_retries": 2,
            "concurrent_fragment_downloads": 4,
            "http_chunk_size": 10485760,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            }],
            "geo_bypass": True,
        }
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_query, download=True)
            if info.get("entries"):
                info = info["entries"][0]
            expected = base + ".mp3"
            if os.path.exists(expected):
                return expected
            fallback = ydl.prepare_filename(info)
            if os.path.exists(fallback):
                return fallback
        return base + ".mp3"

    def scrape_playlist(self, spotify_playlist_link, music_folder):
        playlist_id = extract_playlist_id(spotify_playlist_link)
        self.PlaylistID.emit(playlist_id)

        spotify_api = self.ensure_spotifydown_api()
        metadata = spotify_api.get_playlist_metadata(playlist_id)
        playlist_display_name = self.format_playlist_name(metadata)
        self.song_Album.emit(playlist_display_name)

        playlist_folder_path = self.prepare_playlist_folder(music_folder, playlist_display_name)

        # ── Obtener total de tracks ──────────────────────────────────────────
        all_tracks = list(spotify_api.iter_playlist_tracks(playlist_id))
        total = len(all_tracks)
        # Emitir 0/total para que el contador aparezca desde el inicio
        self.count_updated.emit(0, total)

        for track in all_tracks:
            if self.is_cancelled():
                self.PlaylistCompleted.emit("Download cancelled")
                return

            self.Resetprogress_signal.emit(0)

            track_title = track.title
            artists = track.artists
            filename = f"{self.sanitize_text(track_title)} - {self.sanitize_text(artists)}.mp3"
            filepath = os.path.join(playlist_folder_path, filename)

            song_meta = {
                "title": track_title,
                "artists": artists,
                "album": track.album or "",
                "releaseDate": track.release_date or "",
                "cover": track.cover_url or metadata.cover_url or "",
                "file": filepath,
            }
            self.song_meta.emit(dict(song_meta))

            if os.path.exists(filepath):
                self.add_song_meta.emit(song_meta)
                self.increment_counter(total)
                continue

            search_query = f"ytsearch1:{track_title} {artists} audio"
            try:
                final_path = self.download_track_audio(search_query, filepath)
            except Exception as e:
                self.error_signal.emit(self._get_user_friendly_error(e, track_title))
                self._failed_tracks.append(track_title)
                continue

            if not final_path or not os.path.exists(final_path):
                self._failed_tracks.append(track_title)
                continue

            song_meta["file"] = final_path
            self.add_song_meta.emit(song_meta)
            self.increment_counter(total)
            self.dlprogress_signal.emit(100)

        if self._failed_tracks:
            self.PlaylistCompleted.emit(f"Listo  ({len(self._failed_tracks)} fallaron)")
        else:
            self.PlaylistCompleted.emit("¡Listo!")

    def scrape_track(self, spotify_track_link, music_folder):
        url_type, track_id = detect_spotify_url_type(spotify_track_link)
        if url_type != "track":
            raise ValueError("Expected a track URL")

        spotify_api = self.ensure_spotifydown_api()
        track = spotify_api.get_track(track_id)
        self.song_Album.emit("Single Track Download")
        os.makedirs(music_folder, exist_ok=True)
        self.Resetprogress_signal.emit(0)
        self.count_updated.emit(0, 1)

        track_title = track.title
        artists = track.artists
        filename = f"{self.sanitize_text(track_title)} - {self.sanitize_text(artists)}.mp3"
        filepath = os.path.join(music_folder, filename)

        song_meta = {
            "title": track_title,
            "artists": artists,
            "album": track.album or "",
            "releaseDate": track.release_date or "",
            "cover": track.cover_url or "",
            "file": filepath,
        }
        self.song_meta.emit(dict(song_meta))

        if os.path.exists(filepath):
            self.add_song_meta.emit(song_meta)
            self.increment_counter(1)
            self.PlaylistCompleted.emit("¡Listo!")
            return

        search_query = f"ytsearch1:{track_title} {artists} audio"
        try:
            final_path = self.download_track_audio(search_query, filepath)
        except Exception as e:
            self.PlaylistCompleted.emit(self._get_user_friendly_error(e, track_title))
            return

        if not final_path or not os.path.exists(final_path):
            self.PlaylistCompleted.emit("Download failed")
            return

        song_meta["file"] = final_path
        self.add_song_meta.emit(song_meta)
        self.increment_counter(1)
        self.dlprogress_signal.emit(100)
        self.PlaylistCompleted.emit("¡Listo!")

    def increment_counter(self, total: int):
        self.counter += 1
        self.count_updated.emit(self.counter, total)


# ─────────────────────────────────────────────────────────────────────────────

class ScraperThread(QThread):
    progress_update = pyqtSignal(str)

    def __init__(self, spotify_link, music_folder=None, cancel_event=None):
        super().__init__()
        self.spotify_link = spotify_link
        self.music_folder = music_folder or os.path.join(os.getcwd(), "music")
        self._cancel_event = cancel_event or threading.Event()
        self.scraper = MusicScraper(cancel_event=self._cancel_event)

    def request_cancel(self):
        self._cancel_event.set()

    def run(self):
        self.progress_update.emit("Scraping started...")
        try:
            url_type, _ = detect_spotify_url_type(self.spotify_link)
            if url_type == "track":
                self.scraper.scrape_track(self.spotify_link, self.music_folder)
            else:
                self.scraper.scrape_playlist(self.spotify_link, self.music_folder)
            self.progress_update.emit("Scraping completed.")
        except Exception as e:
            self.progress_update.emit(f"{e}")


class DownloadCover(QThread):
    albumCover = pyqtSignal(object)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        response = requests.get(self.url, stream=True)
        if response.status_code == 200:
            self.albumCover.emit(response.content)


class WritingMetaTagsThread(QThread):
    tags_success = pyqtSignal(str)

    def __init__(self, tags, filename):
        super().__init__()
        self.tags = tags
        self.filename = filename
        self._cover_thread = None

    def run(self):
        try:
            audio = EasyID3(self.filename)
            audio["title"] = self.tags.get("title", "")
            audio["artist"] = self.tags.get("artists", "")
            audio["album"] = self.tags.get("album", "")
            audio["date"] = self.tags.get("releaseDate", "")
            audio.save()
            cover_url = self.tags.get("cover", "")
            if cover_url:
                self._cover_thread = DownloadCover(cover_url)
                self._cover_thread.albumCover.connect(self.setPIC)
                self._cover_thread.start()
        except Exception as e:
            print(f"[*] Error writing meta tags: {e}")

    def setPIC(self, data):
        if data is None:
            self.tags_success.emit("Cover Not Added..!")
        else:
            try:
                audio = ID3(self.filename)
                audio["APIC"] = APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=data)
                audio.save()
                self.tags_success.emit("Tags added successfully")
            except Exception as e:
                self.tags_success.emit(f"Error adding cover: {e}")


class DownloadThumbnail(QThread):
    thumbnail_ready = pyqtSignal(bytes)

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
            pass

    def _update_ui(self, data):
        pic = QImage()
        pic.loadFromData(data)
        self.main_UI.CoverImg.setPixmap(QPixmap(pic))
        self.main_UI.CoverImg.show()


# ─────────────────────────────────────────────────────────────────────────────
# Main Window
# ─────────────────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        # ── Cargar configuración guardada ──────────────────────────────────
        self._config = load_config()
        saved_path = self._config.get("download_path", "")
        if saved_path and os.path.isdir(os.path.dirname(saved_path)):
            self.download_path = saved_path
            self._download_path_set = True
        else:
            self.download_path = self._get_default_download_path()
            self._download_path_set = False

        self._active_threads = []
        self._is_downloading = False
        self._cancel_event = threading.Event()

        # ── Timer para animación de puntos suspensivos ─────────────────────
        self._dot_count = 0
        self._dot_timer = QTimer(self)
        self._dot_timer.setInterval(400)
        self._dot_timer.timeout.connect(self._tick_dots)
        self._dot_base_msg = ""

        # ── Cronómetro de descarga ─────────────────────────────────────────
        self._elapsed_seconds = 0
        self._chrono_timer = QTimer(self)
        self._chrono_timer.setInterval(1000)      # cada segundo
        self._chrono_timer.timeout.connect(self._tick_chrono)

        self.SONGINFORMATION.setGraphicsEffect(
            QGraphicsDropShadowEffect(blurRadius=25, xOffset=2, yOffset=2)
        )
        self.PlaylistLink.returnPressed.connect(self.on_returnButton)
        self.DownloadBtn.clicked.connect(self.on_returnButton)
        self.showPreviewCheck.stateChanged.connect(self.show_preview)
        self.Closed.clicked.connect(self.exitprogram)
        self.Select_Home.clicked.connect(self.Linkedin)
        self.SettingsBtn.clicked.connect(self.open_settings)

    # ── Animación de puntos en Status ─────────────────────────────────────
    def _start_dots(self, base_msg: str):
        self._dot_base_msg = base_msg
        self._dot_count = 0
        self._dot_timer.start()

    def _stop_dots(self):
        self._dot_timer.stop()

    def _tick_dots(self):
        self._dot_count = (self._dot_count % 3) + 1
        self.statusMsg.setText(self._dot_base_msg + "." * self._dot_count)

    # ── Cronómetro ────────────────────────────────────────────────────────
    def _start_chrono(self):
        self._elapsed_seconds = 0
        self.timeLabel.setText("00:00:00")
        self._chrono_timer.start()

    def _stop_chrono(self):
        self._chrono_timer.stop()

    def _tick_chrono(self):
        self._elapsed_seconds += 1
        h = self._elapsed_seconds // 3600
        m = (self._elapsed_seconds % 3600) // 60
        s = self._elapsed_seconds % 60
        self.timeLabel.setText(f"{h:02d}:{m:02d}:{s:02d}")

    # ── Persistencia ──────────────────────────────────────────────────────
    def _save_download_path(self):
        self._config["download_path"] = self.download_path
        save_config(self._config)

    # ── Paths ──────────────────────────────────────────────────────────────
    def _get_default_download_path(self):
        home = os.path.expanduser("~")
        music_folder = os.path.join(home, "Music", "Sunnify")
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
                pass
        return music_folder

    def _ensure_download_path(self):
        try:
            os.makedirs(self.download_path, exist_ok=True)
            test_file = os.path.join(self.download_path, ".sunnify_test")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            return True
        except OSError:
            return False

    def _prompt_download_location(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Download Folder", os.path.expanduser("~"),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
        )
        if folder:
            self.download_path = os.path.join(folder, "Sunnify")
            self._download_path_set = True
            self._save_download_path()        # ← guardar inmediatamente
            return True
        return False

    def open_settings(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Download Folder",
            self.download_path if os.path.exists(self.download_path) else os.path.expanduser("~"),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
        )
        if folder:
            self.download_path = os.path.join(folder, "Sunnify")
            self._download_path_set = True
            self._save_download_path()        # ← guardar al cambiar en settings
            QMessageBox.information(
                self, "Settings Updated",
                f"Download location set to:\n{self.download_path}",
            )

    # ── Botón Download / Stop ──────────────────────────────────────────────
    @pyqtSlot()
    def on_returnButton(self):
        if self._is_downloading:
            self._stop_download()
            return

        spotify_url = self.PlaylistLink.text().strip()
        if not spotify_url:
            self.statusMsg.setText("Please enter a Spotify URL")
            return

        if not self._download_path_set:
            self.statusMsg.setText("Select download location...")
            if not self._prompt_download_location():
                self.statusMsg.setText("Download cancelled - no folder selected")
                return

        if not self._ensure_download_path():
            self.statusMsg.setText("Cannot write to download folder")
            QMessageBox.warning(
                self, "Invalid Download Location",
                f"Cannot write to:\n{self.download_path}\n\nPlease select a different folder.",
            )
            if not self._prompt_download_location():
                return

        try:
            url_type, _ = detect_spotify_url_type(spotify_url)
            self.statusMsg.setText(f"Detected: {url_type}")

            self._cancel_event = threading.Event()
            self._is_downloading = True
            self.DownloadBtn.setText("Stop")
            self._start_chrono()                  # ← arranca el cronómetro

            self.scraper_thread = ScraperThread(
                spotify_url, self.download_path, cancel_event=self._cancel_event
            )
            self.scraper_thread.progress_update.connect(self.update_progress)
            self.scraper_thread.finished.connect(self.thread_finished)
            self.scraper_thread.scraper.song_Album.connect(self.update_AlbumName)
            self.scraper_thread.scraper.song_meta.connect(self.update_song_META)
            self.scraper_thread.scraper.add_song_meta.connect(self.add_song_META)
            self.scraper_thread.scraper.dlprogress_signal.connect(self.update_song_progress)
            self.scraper_thread.scraper.Resetprogress_signal.connect(self.Reset_song_progress)
            self.scraper_thread.scraper.PlaylistCompleted.connect(self.on_playlist_completed)
            self.scraper_thread.scraper.error_signal.connect(lambda x: self.statusMsg.setText(x))
            self.scraper_thread.scraper.count_updated.connect(self.update_counter)

            self.scraper_thread.start()

        except ValueError as e:
            self.statusMsg.setText(str(e))
            self._is_downloading = False
            self.DownloadBtn.setText("Download")

    def _stop_download(self):
        self._stop_dots()
        self._stop_chrono()                       # ← detiene cronómetro
        self.statusMsg.setText("Stopping download...")
        self._cancel_event.set()
        if hasattr(self, "scraper_thread") and self.scraper_thread.isRunning():
            self.scraper_thread.request_cancel()
            if not self.scraper_thread.wait(3000):
                self.scraper_thread.terminate()
                self.scraper_thread.wait(1000)
        self._is_downloading = False
        self.DownloadBtn.setText("Download")
        self.statusMsg.setText("Download stopped")

    def thread_finished(self):
        self._is_downloading = False
        self.DownloadBtn.setText("Download")
        if hasattr(self, "scraper_thread"):
            self.scraper_thread.deleteLater()

    # ── Slots de UI ───────────────────────────────────────────────────────
    def update_progress(self, message):
        self.statusMsg.setText(message)

    @pyqtSlot(int, int)
    def update_counter(self, count: int, total: int):
        """Counter muestra solo el número X/total. Status muestra Descargando..."""
        if total > 0:
            self.CounterLabel.setText(f"{count}/{total}")
            # Arrancar puntos solo al inicio (count==0) o mantenerlos si ya corren
            if not self._dot_timer.isActive():
                self._start_dots("Descargando")
        else:
            self.CounterLabel.setText(str(count))

    @pyqtSlot(str)
    def on_playlist_completed(self, message: str):
        self._stop_dots()
        self._stop_chrono()                       # ← detiene cronómetro al terminar
        self.statusMsg.setText(message)

    @pyqtSlot(dict)
    def update_song_META(self, song_meta):
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
        self.MainSongName.setText(
            song_meta.get("title", "") + " - " + song_meta.get("artists", "")
        )

    @pyqtSlot(dict)
    def add_song_META(self, song_meta):
        if self.AddMetaDataCheck.isChecked():
            meta_thread = WritingMetaTagsThread(song_meta, song_meta["file"])
            meta_thread.tags_success.connect(lambda x: self.statusMsg.setText(f"{x}"))
            self._active_threads.append(meta_thread)
            meta_thread.finished.connect(lambda: self._cleanup_thread(meta_thread))
            meta_thread.start()

    def _cleanup_thread(self, thread):
        if thread in self._active_threads:
            self._active_threads.remove(thread)

    @pyqtSlot(str)
    def update_AlbumName(self, AlbumName):
        self.AlbumName.setText("Playlist Name : " + AlbumName)

    @pyqtSlot(int)
    def update_song_progress(self, progress):
        self.SongDownloadprogressBar.setValue(progress)
        self.SongDownloadprogress.setValue(progress)

    @pyqtSlot(int)
    def Reset_song_progress(self, progress):
        self.SongDownloadprogressBar.setValue(0)
        self.SongDownloadprogress.setValue(0)

    # ── Drag sin barra de título ───────────────────────────────────────────
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
        self.animation.setEndValue(QSize(0, 506))
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.animation.start()

    def OpenSongInformation(self):
        self.animation = QPropertyAnimation(self.SONGINFORMATION, b"size")
        self.animation.setDuration(1000)
        self.animation.setEndValue(QSize(413, 506))
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.animation.start()

    def show_preview(self, state):
        if state == 2:
            self.preview_window = self.OpenSongInformation()
        else:
            self.CloseSongInformation()

    def exitprogram(self):
        sys.exit()

    def Linkedin(self):
        webbrowser.open("https://www.linkedin.com/in/sunny-patel-30b460204/")


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    Screen = MainWindow()
    Screen.setFixedHeight(550)
    Screen.setFixedWidth(825)
    Screen.setWindowFlags(Qt.FramelessWindowHint)
    Screen.setAttribute(Qt.WA_TranslucentBackground)
    Screen.show()
    sys.exit(app.exec())