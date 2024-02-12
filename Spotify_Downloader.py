# 
'''
Copyright (C) Feb 2024 {Sunny Patel} <{sunnypatel124555@gmail.com}>

This file is part of the {Sunnify (Spotify Downloader)} project.

The {Sunnify (Spotify Downloader)} project can not be copied, distributed, and/or modified without the express
permission of {Sunny Patel} <{sunnypatel124555@gmail.com}>.

For the program to work, the playlist URL pattern must be following the format of /playlist/abcdefghijklmnopqrstuvwxyz... (special chars)
will not be registered in the URL as the regex does not specify that in the URL pattern. If the program stops working, email
<{sunnypatel124555@gmail.com}> or open a fork req. in the repository. 
'''

__version__ = "1.0.0"

# Main
# if __name__ == '__main__':from PyQt5.uic import loadUi

from PyQt5.QtWidgets import QMainWindow, QApplication, QGraphicsDropShadowEffect
from PyQt5.QtCore import Qt, QThread, pyqtSignal, pyqtSlot, QSize, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import  QCursor, QImage, QPixmap
from Template import Ui_MainWindow

import sys
import os
import string
import requests
import re
import webbrowser
from mutagen.easyid3 import EasyID3
from mutagen.id3 import APIC, ID3


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

    def get_ID(self, yt_id):
        # The 'get_ID' function from your scraper code
        LINK = f'https://api.spotifydown.com/getId/{yt_id}'
        headers = {
            'authority': 'api.spotifydown.com',
            'method': 'GET',
            'path': f'/getId/{id}',
            'origin': 'https://spotifydown.com',
            'referer': 'https://spotifydown.com/',
            'sec-ch-ua': '"Not_A Brand";v="99", "Google Chrome";v="109", "Chromium";v="109"',
            'sec-fetch-mode': 'cors',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36'
        }
        response = self.session.get(url=LINK, headers=headers)
        if response.status_code == 200:
            data = response.json()
            return data
        return None

    def generate_Analyze_id(self, yt_id):
        # The 'generate_Analyze_id' function from scraper code
        DL = 'https://corsproxy.io/?https://www.y2mate.com/mates/analyzeV2/ajax'
        data = {
            'k_query': f'https://www.youtube.com/watch?v={yt_id}',
            'k_page': 'home',
            'hl': 'en',
            'q_auto': 0,
        }
        headers = {
            'authority': 'corsproxy.io',
            'method': 'POST',
            'path': '/?https://www.y2mate.com/mates/analyzeV2/ajax',
            'origin': 'https://spotifydown.com',
            'referer': 'https://spotifydown.com/',
            'sec-ch-ua': '"Not_A Brand";v="99", "Google Chrome";v="109", "Chromium";v="109"',
            'sec-fetch-mode': 'cors',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36'
        }
        RES = self.session.post(url=DL, data=data, headers=headers)
        if RES.status_code == 200:
            return RES.json()
        return None

    def generate_Conversion_id(self, analyze_yt_id, analyze_id):
        # The 'generate_Conversion_id' function from scraper code
        DL = 'https://corsproxy.io/?https://www.y2mate.com/mates/convertV2/index'
        data = {
            'vid'   : analyze_yt_id,
            'k'     : analyze_id,
        }
        headers = {
            'authority': 'corsproxy.io',
            'method': 'POST',
            'path': '/?https://www.y2mate.com/mates/analyzeV2/ajax',
            'origin': 'https://spotifydown.com',
            'referer': 'https://spotifydown.com/',
            'sec-ch-ua': '"Not_A Brand";v="99", "Google Chrome";v="109", "Chromium";v="109"',
            'sec-fetch-mode': 'cors',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36'
        }
        RES = self.session.post(url=DL, data=data, headers=headers)
        if RES.status_code == 200:
            return RES.json()
        return None

    def get_PlaylistMetadata(self, Playlist_ID):
        # The 'get_PlaylistMetadata' function from scraper code
        URL = f'https://api.spotifydown.com/metadata/playlist/{Playlist_ID}'
        headers = {
            'authority': 'api.spotifydown.com',
            'method': 'GET',
            'path': f'/metadata/playlist/{Playlist_ID}',
            'scheme': 'https',
            'origin': 'https://spotifydown.com',
            'referer': 'https://spotifydown.com/',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36',
        }
        meta_data = self.session.get(headers=headers, url=URL)
        if meta_data.status_code == 200:
            return meta_data.json()['title'] + ' - ' + meta_data.json()['artists']
        return None

    def errorcatch(self, SONG_ID):
        # The 'errorcatch' function from scraper
        print('[*] Trying to download...')
        headers = {
            'authority': 'api.spotifydown.com',
            'method': 'GET',
            'path': f'/download/{SONG_ID}',
            'scheme': 'https',
            'origin': 'https://spotifydown.com',
            'referer': 'https://spotifydown.com/',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36',
        }
        x = self.session.get(headers=headers, url='https://api.spotifydown.com/download/' + SONG_ID)
        if x.status_code == 200:
            return x.json()['link']
        return None



    def V2catch(self, SONG_ID):
        headers = {
            "authority": "api.spotifydown.com",
            "method": "POST",
            "path": '/download/68GdZAAowWDac3SkdNWOwo',
            "scheme": "https",
            "Accept": "*/*",

            'Sec-Ch-Ua':'"Chromium";v="118", "Google Chrome";v="118", "Not=A?Brand";v="99"',
            "Dnt": '1',
            "Origin": "https://spotifydown.com",
            "Referer": "https://spotifydown.com/",
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "cross-site",
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36'
        }

        ## Updated .. .29TH OCTOBER 2023
        x = self.session.get(url = f'https://api.spotifydown.com/download/{SONG_ID}', headers=headers)

        # if x.status_code == 200 (depricated as of Feb 2024):

        #     # par = {
        #     #     'aFormat':'"mp3"',
        #     #     'dubLang':'false',
        #     #     'filenamePattern':'"classic"',
        #     #     'isAudioOnly':'true',
        #     #     'isNoTTWatermark':'true',
        #     #     'url':f'"https%3A%2F%2Fwww.youtube.com%2Fwatch%3Fv%3D{yt_id}"'
        #     # }

        #     file_status = self.session.post(url=f"https://{target_domain}/api/json", json=par, headers=headers)
        # print('[*] Data Gathered : ', str(x.content))
        if x.status_code == 200:

            try:
                return {
                    'link' : x.json()['link'],
                    'metadata' : None
                }
            except:
                return {
                    'link' : None,
                    'metadata' : None
                }

        return None



    def scrape_playlist(self, spotify_playlist_link, music_folder):
        ID = self.returnSPOT_ID(spotify_playlist_link)
        self.PlaylistID.emit(ID)
        PlaylistName = self.get_PlaylistMetadata(ID)
        self.song_Album.emit(PlaylistName)
        # Create Folder for Playlist
        if not os.path.exists(music_folder):
            os.makedirs(music_folder)
        try:
            FolderPath = ''.join(e for e in PlaylistName if e.isalnum() or e in [' ', '_'])
            playlist_folder_path = os.path.join(music_folder, FolderPath)
        except:
            playlist_folder_path = music_folder

        if not os.path.exists(playlist_folder_path):
            os.makedirs(playlist_folder_path)

        headers = {
            'authority': 'api.spotifydown.com',
            'method': 'GET',
            'path': f'/trackList/playlist/{ID}',
            'scheme': 'https',
            'accept': '*/*',
            'dnt': '1',
            'origin': 'https://spotifydown.com',
            'referer': 'https://spotifydown.com/',
            'sec-ch-ua': '"Chromium";v="110", "Not A(Brand";v="24", "Google Chrome";v="110"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
        }

        Playlist_Link = f'https://api.spotifydown.com/trackList/playlist/{ID}'
        offset_data = {}
        offset = 0
        offset_data['offset'] = offset

        while offset is not None:
            response = self.session.get(url=Playlist_Link, params=offset_data, headers=headers)
            if response.status_code == 200:
                Tdata = response.json()['trackList']
                page = response.json()['nextOffset']
                for count, song in enumerate(Tdata):
                    self.Resetprogress_signal.emit(0)
                    filename = song['title'].translate(str.maketrans('', '', string.punctuation)) + ' - ' + song['artists'].translate(str.maketrans('', '', string.punctuation)) + '.mp3'
                    filepath = os.path.join(playlist_folder_path, filename)
                    try:
                        try:
                            V2METHOD    = self.V2catch(song['id'])
                            DL_LINK     = V2METHOD['link']
                            SONG_META   = song
                            SONG_META['file'] = filepath
                            self.song_meta.emit(SONG_META)
                        except IndentationError:
                            yt_id = self.get_ID(song['id'])

                            if yt_id is not None:
                                data = self.generate_Analyze_id(yt_id['id'])
                                try:
                                    DL_ID = data['links']['mp3']['mp3128']['k']
                                    DL_DATA = self.generate_Conversion_id(data['vid'], DL_ID)
                                    DL_LINK = DL_DATA['dlink']
                                except Exception as NoLinkError:
                                    CatchMe = self.errorcatch(song['id'])
                                    if CatchMe is not None:
                                        DL_LINK = CatchMe
                            else:
                                print('[*] No data found for : ', song)

                        download_complete = False
                        if DL_LINK is not None:
                            ## DOWNLOAD
                            link = self.session.get(DL_LINK, stream=True)
                            total_size = int(link.headers.get('content-length', 0))
                            block_size = 1024  # 1 Kilobyte
                            downloaded = 0
                            ## Save
                            with open(filepath, "wb") as f:
                                for data in link.iter_content(block_size):
                                    f.write(data)
                                    downloaded += len(data)
                                    # self.dlprogress_signal.emit(int(100 * downloaded / total_size))


                            #Increment the counter
                            self.increment_counter()

                            # # Emit the signal with the downloaded song name
                            self.add_song_meta.emit(SONG_META)
                        else:
                            print('[*] No Download Link Found.')
                    except Exception as error_status:
                        print('[*] Error Status Code : ', error_status)
            if page is not None:
                offset_data['offset'] = page
                response = self.session.get(url=Playlist_Link, params=offset_data, headers=headers)
            else:
                self.PlaylistCompleted.emit('Download Complete!')
                break

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
        music_folder = os.path.join(os.getcwd(), "music")  # Change this path to your desired music folder
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
        if response.status_code == 200 :
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
            print('[*] FileName : ', self.filename)
            audio = EasyID3(self.filename)
            audio['title'] = self.tags['title']
            audio['artist'] = self.tags['artists']
            audio['album'] = self.tags['album']
            audio['date'] = self.tags['releaseDate']
            audio.save()
            # self.tags_success.emit("Meta added!")
            # self.tags_success.emit("Adding Cover")
            self.CoverPic = DownloadCover(self.tags['cover']+"?size=1")
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
                audio['APIC'] = APIC(
                    encoding=3,
                    mime='image/jpeg',
                    type=3,
                    desc=u'Cover',
                    data=data
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
        if response.status_code == 200 :
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

        self.SONGINFORMATION.setGraphicsEffect(QGraphicsDropShadowEffect(blurRadius=25,xOffset=2,yOffset=2))
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
            self.scraper_thread.finished.connect(self.thread_finished)  # Connect the finished signal
            self.scraper_thread.scraper.song_Album.connect(self.update_AlbumName)  # Connect the signal
            self.scraper_thread.scraper.song_meta.connect(self.update_song_META)  # Connect the signal
            self.scraper_thread.scraper.add_song_meta.connect(self.add_song_META)  # Connect the signal


            self.scraper_thread.scraper.dlprogress_signal.connect(self.update_song_progress)  # Download Progress
            self.scraper_thread.scraper.Resetprogress_signal.connect(self.Reset_song_progress)  # Download Progress
            self.scraper_thread.scraper.PlaylistCompleted.connect(lambda x: self.statusMsg.setText(x))

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
            self.thumbnail_thread = DownloadThumbnail(song_meta['cover']+"?size=1", self)
            self.thumbnail_thread.start()
            self.ArtistNameText.setText(song_meta['artists'])
            self.AlbumText.setText(song_meta['album'])
            self.SongName.setText(song_meta['title'])
            self.YearText.setText(song_meta['releaseDate'])
        else:
            pass

        self.MainSongName.setText(song_meta['title'] + ' - ' + song_meta['artists'])
        if self.AddMetaDataCheck.isChecked():
            self.meta_thread = WritingMetaTagsThread(song_meta, song_meta['file'])
            self.meta_thread.tags_success.connect(lambda x:self.statusMsg.setText("{}".format(x)))
            self.meta_thread.start()



    @pyqtSlot(dict)
    def add_song_META(self, song_meta):
        if self.AddMetaDataCheck.isChecked():
            self.meta_thread = WritingMetaTagsThread(song_meta, song_meta['file'])
            self.meta_thread.tags_success.connect(lambda x:self.statusMsg.setText("{}".format(x)))
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
        self.animation.setEndValue(QSize(0,330))
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.animation.start()

    def OpenSongInformation(self):
        self.animation = QPropertyAnimation(self.SONGINFORMATION, b"size")
        self.animation.setDuration(1000)
        self.animation.setEndValue(QSize(270,330))
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
        webbrowser.open('https://www.linkedin.com/in/sunny-patel-30b460204/')

# Main
if __name__ == '__main__':
    app = QApplication(sys.argv)
    Screen = MainWindow()
    Screen.setFixedHeight(390)
    Screen.setFixedWidth(600)
    Screen.setWindowFlags(Qt.FramelessWindowHint)
    Screen.setAttribute(Qt.WA_TranslucentBackground)
    Screen.show()
    sys.exit(app.exec())


