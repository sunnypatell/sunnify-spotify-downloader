from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import string
import requests
import re
from mutagen.easyid3 import EasyID3
from mutagen.id3 import APIC, ID3

app = Flask(__name__)
CORS(app)

class MusicScraper:
    def __init__(self):
        self.counter = 0  # Initialize counter to zero
        self.session = requests.Session()

    def get_ID(self, yt_id):
        # The 'get_ID' function from your scraper code
        LINK = f"https://api.spotifydown.com/getId/{yt_id}"
        headers = {
            "authority": "api.spotifydown.com",
            "method": "GET",
            "path": f"/getId/{yt_id}",
            "origin": "https://spotifydown.com",
            "referer": "https://spotifydown.com/",
            "sec-ch-ua": '"Not_A Brand";v="99", "Google Chrome";v="109", "Chromium";v="109"',
            "sec-fetch-mode": "cors",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
        }
        response = self.session.get(url=LINK, headers=headers)
        if response.status_code == 200:
            data = response.json()
            return data
        return None

    def generate_Analyze_id(self, yt_id):
        # The 'generate_Analyze_id' function from scraper code
        DL = "https://corsproxy.io/?https://www.y2mate.com/mates/analyzeV2/ajax"
        data = {
            "k_query": f"https://www.youtube.com/watch?v={yt_id}",
            "k_page": "home",
            "hl": "en",
            "q_auto": 0,
        }
        headers = {
            "authority": "corsproxy.io",
            "method": "POST",
            "path": "/?https://www.y2mate.com/mates/analyzeV2/ajax",
            "origin": "https://spotifydown.com",
            "referer": "https://spotifydown.com/",
            "sec-ch-ua": '"Not_A Brand";v="99", "Google Chrome";v="109", "Chromium";v="109"',
            "sec-fetch-mode": "cors",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
        }
        RES = self.session.post(url=DL, data=data, headers=headers)
        if RES.status_code == 200:
            return RES.json()
        return None

    def generate_Conversion_id(self, analyze_yt_id, analyze_id):
        # The 'generate_Conversion_id' function from scraper code
        DL = "https://corsproxy.io/?https://www.y2mate.com/mates/convertV2/index"
        data = {
            "vid": analyze_yt_id,
            "k": analyze_id,
        }
        headers = {
            "authority": "corsproxy.io",
            "method": "POST",
            "path": "/?https://www.y2mate.com/mates/analyzeV2/ajax",
            "origin": "https://spotifydown.com",
            "referer": "https://spotifydown.com/",
            "sec-ch-ua": '"Not_A Brand";v="99", "Google Chrome";v="109", "Chromium";v="109"',
            "sec-fetch-mode": "cors",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
        }
        RES = self.session.post(url=DL, data=data, headers=headers)
        if RES.status_code == 200:
            return RES.json()
        return None

    def get_PlaylistMetadata(self, Playlist_ID):
        # The 'get_PlaylistMetadata' function from scraper code
        URL = f"https://api.spotifydown.com/metadata/playlist/{Playlist_ID}"
        headers = {
            "authority": "api.spotifydown.com",
            "method": "GET",
            "path": f"/metadata/playlist/{Playlist_ID}",
            "scheme": "https",
            "origin": "https://spotifydown.com",
            "referer": "https://spotifydown.com/",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36",
        }
        meta_data = self.session.get(headers=headers, url=URL)
        if meta_data.status_code == 200:
            return meta_data.json()["title"] + " - " + meta_data.json()["artists"]
        return None

    def errorcatch(self, SONG_ID):
        # The 'errorcatch' function from scraper
        print("[*] Trying to download...")
        headers = {
            "authority": "api.spotifydown.com",
            "method": "GET",
            "path": f"/download/{SONG_ID}",
            "scheme": "https",
            "origin": "https://spotifydown.com",
            "referer": "https://spotifydown.com/",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36",
        }
        x = self.session.get(
            headers=headers, url="https://api.spotifydown.com/download/" + SONG_ID
        )
        if x.status_code == 200:
            return x.json()["link"]
        return None

    def V2catch(self, SONG_ID):
        headers = {
            "authority": "api.spotifydown.com",
            "method": "POST",
            "path": "/download/68GdZAAowWDac3SkdNWOwo",
            "scheme": "https",
            "Accept": "*/*",
            "Sec-Ch-Ua": '"Chromium";v="118", "Google Chrome";v="118", "Not=A?Brand";v="99"',
            "Dnt": "1",
            "Origin": "https://spotifydown.com",
            "Referer": "https://spotifydown.com/",
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "cross-site",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
        }

        x = self.session.get(
            url=f"https://api.spotifydown.com/download/{SONG_ID}", headers=headers
        )
        if x.status_code == 200:
            try:
                return {"link": x.json()["link"], "metadata": None}
            except:
                return {"link": None, "metadata": None}

        return None

    def scrape_playlist(self, spotify_playlist_link, music_folder):
        ID = self.returnSPOT_ID(spotify_playlist_link)
        PlaylistName = self.get_PlaylistMetadata(ID)

        # Create Folder for Playlist
        if not os.path.exists(music_folder):
            os.makedirs(music_folder)
        try:
            FolderPath = "".join(
                e for e in PlaylistName if e.isalnum() or e in [" ", "_"]
            )
            playlist_folder_path = os.path.join(music_folder, FolderPath)
        except:
            playlist_folder_path = music_folder

        if not os.path.exists(playlist_folder_path):
            os.makedirs(playlist_folder_path)

        headers = {
            "authority": "api.spotifydown.com",
            "method": "GET",
            "path": f"/trackList/playlist/{ID}",
            "scheme": "https",
            "accept": "*/*",
            "dnt": "1",
            "origin": "https://spotifydown.com",
            "referer": "https://spotifydown.com/",
            "sec-ch-ua": '"Chromium";v="110", "Not A(Brand";v="24", "Google Chrome";v="110"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
        }

        Playlist_Link = f"https://api.spotifydown.com/trackList/playlist/{ID}"
        offset_data = {}
        offset = 0
        offset_data["offset"] = offset

        while offset is not None:
            response = self.session.get(
                url=Playlist_Link, params=offset_data, headers=headers
            )
            if response.status_code == 200:
                Tdata = response.json()["trackList"]
                page = response.json()["nextOffset"]
                for count, song in enumerate(Tdata):
                    filename = (
                        song["title"].translate(
                            str.maketrans("", "", string.punctuation)
                        )
                        + " - "
                        + song["artists"].translate(
                            str.maketrans("", "", string.punctuation)
                        )
                        + ".mp3"
                    )
                    filepath = os.path.join(playlist_folder_path, filename)
                    try:
                        try:
                            V2METHOD = self.V2catch(song["id"])
                            DL_LINK = V2METHOD["link"]
                        except IndentationError:
                            yt_id = self.get_ID(song["id"])

                            if yt_id is not None:
                                data = self.generate_Analyze_id(yt_id["id"])
                                try:
                                    DL_ID = data["links"]["mp3"]["mp3128"]["k"]
                                    DL_DATA = self.generate_Conversion_id(
                                        data["vid"], DL_ID
                                    )
                                    DL_LINK = DL_DATA["dlink"]
                                except Exception as NoLinkError:
                                    CatchMe = self.errorcatch(song["id"])
                                    if CatchMe is not None:
                                        DL_LINK = CatchMe
                            else:
                                print("[*] No data found for : ", song)

                        if DL_LINK is not None:
                            ## DOWNLOAD
                            link = self.session.get(DL_LINK, stream=True)
                            with open(filepath, "wb") as f:
                                for data in link.iter_content(1024):
                                    f.write(data)
                        else:
                            print("[*] No Download Link Found.")
                    except Exception as error_status:
                        print("[*] Error Status Code : ", error_status)
            if page is not None:
                offset_data["offset"] = page
                response = self.session.get(
                    url=Playlist_Link, params=offset_data, headers=headers
                )
            else:
                break

    def returnSPOT_ID(self, link):
        pattern = r"https://open\.spotify\.com/playlist/([a-zA-Z0-9]+)"
        match = re.match(pattern, link)

        if not match:
            raise ValueError("Invalid Spotify playlist URL.")
        extracted_id = match.group(1)

        return extracted_id

@app.route('/scrape_playlist', methods=['POST'])
def scrape_playlist():
    data = request.get_json()
    spotify_playlist_link = data.get("playlist_link")
    music_folder = os.path.join(os.getcwd(), "music")

    scraper = MusicScraper()
    try:
        scraper.scrape_playlist(spotify_playlist_link, music_folder)
        return jsonify({"status": "success", "message": "Scraping completed."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(directory='music', filename=filename)

if __name__ == '__main__':
    app.run(debug=True)
