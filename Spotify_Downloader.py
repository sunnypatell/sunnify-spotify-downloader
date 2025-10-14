#
"""
Copyright (C) Feb 2024 {Sunny Patel} <{sunnypatel124555@gmail.com}>

This file is part of the {Sunnify (Spotify Downloader)} project.

The {Sunnify (Spotify Downloader)} project can not be copied, distributed, and/or modified without the express
permission of {Sunny Patel} <{sunnypatel124555@gmail.com}>.

For the program to work, the playlist URL pattern must be following the format of /playlist/abcdefghijklmnopqrstuvwxyz... (special chars)
will not be registered in the URL as the regex does not specify that in the URL pattern. If the program stops working, email
<{sunnypatel124555@gmail.com}> or open a fork req. in the repository. 
"""

__version__ = "1.0.0"

# Main
# if __name__ == '__main__':from PyQt5.uic import loadUi

from PyQt5.QtWidgets import QMainWindow, QApplication, QGraphicsDropShadowEffect
from PyQt5.QtCore import (
    Qt,
    QThread,
    pyqtSignal,
    pyqtSlot,
    QSize,
    QPropertyAnimation,
    QEasingCurve,
)
from PyQt5.QtGui import QCursor, QImage, QPixmap
from Template import Ui_MainWindow

import sys
import os
import string
import requests
import re
import webbrowser
from mutagen.easyid3 import EasyID3
from mutagen.id3 import APIC, ID3
from yt_dlp import YoutubeDL

from spotifydown_api import PlaylistInfo, SpotifyDownAPI, SpotifyDownAPIError


class MusicScraper(QThread):
    PlaylistCompleted = pyqtSignal(str)
    PlaylistID = pyqtSignal(str)
    song_Album = pyqtSignal(str)
    song_meta = pyqtSignal(dict)
    add_song_meta = pyqtSignal(dict)
    count_updated = pyqtSignal(int)
    dlprogress_signal = pyqtSignal(int)
    Resetprogress_signal = pyqtSignal(int)

    def __init__(self):
        super(MusicScraper, self).__init__()
        self.counter = 0  # Initialize counter to zero
        self.session = requests.Session()
        self.spotifydown_api = None

    def ensure_spotifydown_api(self):
        if self.spotifydown_api is None:
            self.spotifydown_api = SpotifyDownAPI(session=self.session)
        return self.spotifydown_api

    def sanitize_text(self, text):
        cleaned = text.translate(str.maketrans("", "", string.punctuation))
        normalized = " ".join(cleaned.split())
        return normalized or "Unknown"

    def format_playlist_name(self, metadata: PlaylistInfo):
        owner = metadata.owner or "Spotify"
        return f"{metadata.name} - {owner}".strip(" -")

    def prepare_playlist_folder(self, base_folder, playlist_name):
        if not os.path.exists(base_folder):
            os.makedirs(base_folder)
        safe_name = "".join(
            character for character in playlist_name if character.isalnum() or character in [" ", "_"]
        ).strip()
        if not safe_name:
            safe_name = "Sunnify Playlist"
        playlist_folder = os.path.join(base_folder, safe_name)
        os.makedirs(playlist_folder, exist_ok=True)
        return playlist_folder

    def download_track_audio(self, search_query, destination):
        base, _ = os.path.splitext(destination)
        output_template = base + ".%(ext)s"
        ydl_opts = {
            "format": "bestaudio/best",
            "noplaylist": True,
            "quiet": True,
            "outtmpl": output_template,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
        }
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_query, download=True)
            if info.get("entries"):
                info = info["entries"][0]
            expected_path = base + ".mp3"
            if os.path.exists(expected_path):
                return expected_path
            fallback = ydl.prepare_filename(info)
            if os.path.exists(fallback):
                return fallback
        return base + ".mp3"

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


    def scrape_playlist(self, spotify_playlist_link, music_folder):
        playlist_id = self.returnSPOT_ID(spotify_playlist_link)
        self.PlaylistID.emit(playlist_id)

        try:
            spotify_api = self.ensure_spotifydown_api()
        except SpotifyDownAPIError as exc:
            raise RuntimeError(str(exc))

        metadata = spotify_api.get_playlist_metadata(playlist_id)
        playlist_display_name = self.format_playlist_name(metadata)
        self.song_Album.emit(playlist_display_name)

        playlist_folder_path = self.prepare_playlist_folder(music_folder, playlist_display_name)

        for track in spotify_api.iter_playlist_tracks(playlist_id):
            self.Resetprogress_signal.emit(0)

            track_title = track.title
            artists = track.artists
            sanitized_title = self.sanitize_text(track_title)
            sanitized_artists = self.sanitize_text(artists)
            filename = f"{sanitized_title} - {sanitized_artists}.mp3"
            filepath = os.path.join(playlist_folder_path, filename)

            album_name = track.album or ""
            release_date = track.release_date or ""
            cover_url = track.cover_url or metadata.cover_url

            song_meta = {
                "title": track_title,
                "artists": artists,
                "album": album_name,
                "releaseDate": release_date,
                "cover": cover_url or "",
                "file": filepath,
            }

            self.song_meta.emit(dict(song_meta))

            if os.path.exists(filepath):
                self.add_song_meta.emit(song_meta)
                self.increment_counter()
                continue

            final_path = None

            try:
                download_link = spotify_api.get_track_download_link(track.id)
            except SpotifyDownAPIError:
                download_link = None

            if download_link:
                try:
                    final_path = self.download_http_file(download_link, filepath)
                except Exception as error_status:
                    print("[*] Error downloading direct link:", error_status)
                    final_path = None

            if not final_path:
                try:
                    yt_id = spotify_api.get_track_youtube_id(track.id)
                except SpotifyDownAPIError:
                    yt_id = None

                if yt_id:
                    search_query = f"https://www.youtube.com/watch?v={yt_id}"
                else:
                    search_query = f"ytsearch1:{track_title} {artists} audio"

                try:
                    final_path = self.download_track_audio(search_query, filepath)
                except Exception as error_status:
                    print("[*] Error downloading track:", error_status)
                    continue

            if not os.path.exists(final_path):
                print("[*] Download did not produce an audio file for:", track_title)
                continue

            song_meta["file"] = final_path
            self.add_song_meta.emit(song_meta)
            self.increment_counter()
            self.dlprogress_signal.emit(100)

        self.PlaylistCompleted.emit("Download Complete!")

    def returnSPOT_ID(self, link):
        # # The 'returnSPOT_ID' function from your scraper code
        # return link.split('/')[-1].split('?si')[0]

        # Define the regular expression pattern for the Spotify playlist URL
        pattern = r"https://open\.spotify\.com/playlist/([a-zA-Z0-9]+)"

        # Try to match the pattern in the input text
        match = re.match(pattern, link)

        if not match:
            raise ValueError("Invalid Spotify playlist URL.")
        # Extract the playlist ID from the matched pattern
        extracted_id = match.group(1)

        return extracted_id

    def increment_counter(self):
        self.counter += 1
        self.count_updated.emit(self.counter)  # Emit the signal with the updated count


# Scraper Thread
class ScraperThread(QThread):
    progress_update = pyqtSignal(str)

    def __init__(self, playlist_link):
        super().__init__()
        self.playlist_link = playlist_link
        self.scraper = MusicScraper()  # Create an instance of MusicScraper

    def run(self):
        music_folder = os.path.join(
            os.getcwd(), "music"
        )  # Change this path to your desired music folder
        self.progress_update.emit("Scraping started...")
        try:
            self.scraper.returnSPOT_ID(self.playlist_link)
            self.scraper.scrape_playlist(self.playlist_link, music_folder)
            self.progress_update.emit("Scraping completed.")
        except Exception as e:
            self.progress_update.emit(f"{e}")


# Download Song Cover Thread
class DownloadCover(QThread):
    albumCover = pyqtSignal(object)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        response = requests.get(self.url, stream=True)
        if response.status_code == 200:
            self.albumCover.emit(response.content)


# Scraper Thread
class WritingMetaTagsThread(QThread):
    tags_success = pyqtSignal(str)

    def __init__(self, tags, filename):
        super().__init__()
        self.tags = tags
        self.filename = filename
        self.PICTUREDATA = None

    def run(self):
        # self.tags_success.emit("Writing Metatags")
        try:
            print("[*] FileName : ", self.filename)
            audio = EasyID3(self.filename)
            audio["title"] = self.tags["title"]
            audio["artist"] = self.tags["artists"]
            audio["album"] = self.tags["album"]
            audio["date"] = self.tags["releaseDate"]
            audio.save()
            # self.tags_success.emit("Meta added!")
            # self.tags_success.emit("Adding Cover")
            self.CoverPic = DownloadCover(self.tags["cover"] + "?size=1")
            self.CoverPic.albumCover.connect(self.setPIC)
            self.CoverPic.start()
        except Exception as e:
            pass
            # print(f'Error {e}')
            # self.tags_success.emit(f"Error in FIle : {e}")

    def setPIC(self, data):
        if data is None:
            self.tags_success.emit("Cover Not Added..!")
        else:
            try:
                audio = ID3(self.filename)
                audio["APIC"] = APIC(
                    encoding=3, mime="image/jpeg", type=3, desc="Cover", data=data
                )
                audio.save()
                # self.tags_success.emit("Cover Added..!")
            except Exception as e:
                self.tags_success.emit(f"Error adding cover: {e}")


class DownloadThumbnail(QThread):

    def __init__(self, url, main_UI):
        super().__init__()
        self.url = url
        self.main_UI = main_UI

    def run(self):
        response = requests.get(self.url, stream=True)
        if response.status_code == 200:
            pic = QImage()
            pic.loadFromData(response.content)
            self.main_UI.CoverImg.setPixmap(QPixmap(pic))
            self.main_UI.CoverImg.show()


# Main Window
class MainWindow(QMainWindow, Ui_MainWindow):
    # class MainWindow(QMainWindow):

    def __init__(self):
        """MainWindow constructor"""
        super(MainWindow, self).__init__()

        # Main UI code goes here
        # loadUi("Template.ui", self)

        self.setupUi(self)

        self.SONGINFORMATION.setGraphicsEffect(
            QGraphicsDropShadowEffect(blurRadius=25, xOffset=2, yOffset=2)
        )
        self.PlaylistLink.returnPressed.connect(self.on_returnButton)

        self.showPreviewCheck.stateChanged.connect(self.show_preview)

        self.Closed.clicked.connect(self.exitprogram)
        self.Select_Home.clicked.connect(self.Linkedin)
        # End main UI code

    # https://open.spotify.com/playlist/37i9dQZF1E36hkEAnydKTA?si=20caa5adfed648d3

    @pyqtSlot()
    def on_returnButton(self):
        playlist_id = self.PlaylistLink.text()
        try:
            # self.PlaylistMsg.setText('Playlist Code : %s' % playlist_id)

            # Start the scraper in a separate thread
            self.scraper_thread = ScraperThread(playlist_id)
            # self.scraper_thread.scraper.PlaylistID.connect(lambda x:self.PlaylistMsg.setText("Playlist Code : {}".format(x)))  # Connect the signal
            self.scraper_thread.progress_update.connect(self.update_progress)
            self.scraper_thread.finished.connect(
                self.thread_finished
            )  # Connect the finished signal
            self.scraper_thread.scraper.song_Album.connect(
                self.update_AlbumName
            )  # Connect the signal
            self.scraper_thread.scraper.song_meta.connect(
                self.update_song_META
            )  # Connect the signal
            self.scraper_thread.scraper.add_song_meta.connect(
                self.add_song_META
            )  # Connect the signal

            self.scraper_thread.scraper.dlprogress_signal.connect(
                self.update_song_progress
            )  # Download Progress
            self.scraper_thread.scraper.Resetprogress_signal.connect(
                self.Reset_song_progress
            )  # Download Progress
            self.scraper_thread.scraper.PlaylistCompleted.connect(
                lambda x: self.statusMsg.setText(x)
            )

            # Connect the count_updated signal to the update_counter slot
            self.scraper_thread.scraper.count_updated.connect(self.update_counter)

            self.scraper_thread.start()

        except ValueError as e:
            self.statusMsg.setText(str(e))

    def thread_finished(self):
        self.scraper_thread.deleteLater()  # Clean up the thread properly

    def update_progress(self, message):
        self.statusMsg.setText(message)

    @pyqtSlot(dict)
    def update_song_META(self, song_meta):

        if self.showPreviewCheck.isChecked():
            self.thumbnail_thread = DownloadThumbnail(
                song_meta["cover"] + "?size=1", self
            )
            self.thumbnail_thread.start()
            self.ArtistNameText.setText(song_meta["artists"])
            self.AlbumText.setText(song_meta["album"])
            self.SongName.setText(song_meta["title"])
            self.YearText.setText(song_meta["releaseDate"])
        else:
            pass

        self.MainSongName.setText(song_meta["title"] + " - " + song_meta["artists"])
        if self.AddMetaDataCheck.isChecked():
            self.meta_thread = WritingMetaTagsThread(song_meta, song_meta["file"])
            self.meta_thread.tags_success.connect(
                lambda x: self.statusMsg.setText("{}".format(x))
            )
            self.meta_thread.start()

    @pyqtSlot(dict)
    def add_song_META(self, song_meta):
        if self.AddMetaDataCheck.isChecked():
            self.meta_thread = WritingMetaTagsThread(song_meta, song_meta["file"])
            self.meta_thread.tags_success.connect(
                lambda x: self.statusMsg.setText("{}".format(x))
            )
            self.meta_thread.start()

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
        except:
            pass

    def mouseReleaseEvent(self, QMouseEvent):
        self.m_drag = False
        self.setCursor(QCursor(Qt.ArrowCursor))

    def CloseSongInformation(self):
        self.animation = QPropertyAnimation(self.SONGINFORMATION, b"size")
        self.animation.setDuration(250)
        self.animation.setEndValue(QSize(0, 330))
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.animation.start()

    def OpenSongInformation(self):
        self.animation = QPropertyAnimation(self.SONGINFORMATION, b"size")
        self.animation.setDuration(1000)
        self.animation.setEndValue(QSize(270, 330))
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
    Screen.setFixedHeight(390)
    Screen.setFixedWidth(600)
    Screen.setWindowFlags(Qt.FramelessWindowHint)
    Screen.setAttribute(Qt.WA_TranslucentBackground)
    Screen.show()
    sys.exit(app.exec())
