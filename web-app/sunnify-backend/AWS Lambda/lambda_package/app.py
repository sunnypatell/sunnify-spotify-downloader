from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
import os
import string
import requests
import re
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, APIC
import json
from mangum import Mangum  # Import Mangum for AWS Lambda

app = Flask(__name__)
CORS(app)  # Enable CORS for cross-origin requests

class MusicScraper:
    def __init__(self):
        self.session = requests.Session()

    def get_ID(self, yt_id):
        LINK = f"https://api.spotifydown.com/getId/{yt_id}"
        headers = {
            "authority": "api.spotifydown.com",
            "method": "GET",
            "origin": "https://spotifydown.com",
            "referer": "https://spotifydown.com/",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
        response = self.session.get(url=LINK, headers=headers)
        if response.status_code == 200:
            return response.json()
        return None

    def generate_Analyze_id(self, yt_id):
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
            "origin": "https://spotifydown.com",
            "referer": "https://spotifydown.com/",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
        RES = self.session.post(url=DL, data=data, headers=headers)
        if RES.status_code == 200:
            return RES.json()
        return None

    def generate_Conversion_id(self, analyze_yt_id, analyze_id):
        DL = "https://corsproxy.io/?https://www.y2mate.com/mates/convertV2/index"
        data = {
            "vid": analyze_yt_id,
            "k": analyze_id,
        }
        headers = {
            "authority": "corsproxy.io",
            "method": "POST",
            "origin": "https://spotifydown.com",
            "referer": "https://spotifydown.com/",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
        RES = self.session.post(url=DL, data=data, headers=headers)
        if RES.status_code == 200:
            return RES.json()
        return None

    def get_PlaylistMetadata(self, Playlist_ID):
        URL = f"https://api.spotifydown.com/metadata/playlist/{Playlist_ID}"
        headers = {
            "authority": "api.spotifydown.com",
            "method": "GET",
            "origin": "https://spotifydown.com",
            "referer": "https://spotifydown.com/",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
        meta_data = self.session.get(headers=headers, url=URL)
        if meta_data.status_code == 200:
            return meta_data.json()["title"] + " - " + meta_data.json()["artists"]
        return None

    def V2catch(self, SONG_ID):
        headers = {
            "authority": "api.spotifydown.com",
            "method": "POST",
            "path": "/download/68GdZAAowWDac3SkdNWOwo",
            "Accept": "*/*",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }

        x = self.session.get(
            url=f"https://api.spotifydown.com/download/{SONG_ID}", headers=headers
        )
        if x.status_code == 200:
            try:
                return {"link": x.json()["link"], "metadata": x.json()}
            except:
                return {"link": None, "metadata": None}
        return None

    def scrape_playlist(self, spotify_playlist_link, music_folder):
        try:
            ID = self.returnSPOT_ID(spotify_playlist_link)
            PlaylistName = self.get_PlaylistMetadata(ID)

            FolderPath = "".join(
                e for e in PlaylistName if e.isalnum() or e in [" ", "_"]
            )
            playlist_folder_path = os.path.join(music_folder, FolderPath)
            
            if not os.path.exists(playlist_folder_path):
                os.makedirs(playlist_folder_path)

            headers = {
                "authority": "api.spotifydown.com",
                "method": "GET",
                "path": f"/trackList/playlist/{ID}",
                "origin": "https://spotifydown.com",
                "referer": "https://spotifydown.com/",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            }

            Playlist_Link = f"https://api.spotifydown.com/trackList/playlist/{ID}"
            offset_data = {}
            offset = 0
            offset_data["offset"] = offset

            downloaded_tracks = []
            total_tracks = 0

            while offset is not None:
                response = self.session.get(
                    url=Playlist_Link, params=offset_data, headers=headers
                )
                if response.status_code == 200:
                    Tdata = response.json()["trackList"]
                    page = response.json()["nextOffset"]
                    total_tracks += len(Tdata)
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
                            V2METHOD = self.V2catch(song["id"])
                            DL_LINK = V2METHOD["link"]
                            metadata = V2METHOD["metadata"]

                            if DL_LINK is not None:
                                link = self.session.get(DL_LINK, stream=True)
                                with open(filepath, "wb") as f:
                                    for data in link.iter_content(1024):
                                        f.write(data)
                            
                                self.write_metadata(filepath, song, metadata)
                                downloaded_tracks.append({
                                    "id": song["id"],
                                    "title": song["title"],
                                    "artists": song["artists"],
                                    "album": song.get("album", ""),
                                    "cover": song.get("cover", ""),
                                    "releaseDate": song.get("releaseDate", ""),
                                    "downloadLink": f"/api/download/{filename}"
                                })

                                yield {
                                    "event": "progress",
                                    "data": {
                                        "progress": len(downloaded_tracks) / total_tracks * 100,
                                        "currentTrack": {
                                            "title": song["title"],
                                            "artists": song["artists"]
                                        }
                                    }
                                }

                        except Exception as error_status:
                            print("[*] Error Status Code : ", error_status)
                            yield {
                                "event": "error",
                                "data": {
                                    "message": f"Error downloading {song['title']}: {str(error_status)}"
                                }
                            }

                if page is not None:
                    offset_data["offset"] = page
                else:
                    break

            yield {
                "event": "complete",
                "data": {
                    "playlistName": PlaylistName,
                    "tracks": downloaded_tracks
                }
            }
        except Exception as e:
            yield {
                "event": "error",
                "data": {
                    "message": f"An error occurred while processing the playlist: {str(e)}"
                }
            }

    def write_metadata(self, filepath, song_meta, additional_meta):
        try:
            audio = EasyID3(filepath)
            audio["title"] = song_meta.get("title", "Unknown Title")
            audio["artist"] = song_meta.get("artists", "Unknown Artist")
            audio["album"] = song_meta.get("album", "Unknown Album")
            audio["date"] = song_meta.get("releaseDate", "")
            audio.save()

            if additional_meta and "cover" in additional_meta:
                cover_url = additional_meta["cover"]
                cover_response = self.session.get(cover_url)
                if cover_response.status_code == 200:
                    audio = ID3(filepath)
                    audio["APIC"] = APIC(
                        encoding=3,
                        mime="image/jpeg",
                        type=3,
                        desc="Cover",
                        data=cover_response.content
                    )
                    audio.save()

        except Exception as e:
            print(f"Error writing metadata: {e}")

    def returnSPOT_ID(self, link):
        pattern = r"https://open\.spotify\.com/playlist/([a-zA-Z0-9]+)"
        match = re.match(pattern, link)

        if not match:
            raise ValueError("Invalid Spotify playlist URL.")
        extracted_id = match.group(1)

        return extracted_id

@app.route('/api/scrape-playlist', methods=['POST'])
def scrape_playlist():
    data = request.get_json()
    spotify_playlist_link = data.get("playlistUrl")
    download_path = data.get("downloadPath", "")

    if not download_path:
        return jsonify({"error": "Download path not specified"}), 400

    if not os.path.exists(download_path):
        return jsonify({"error": "Specified download path does not exist"}), 400

    if not os.access(download_path, os.W_OK):
        return jsonify({"error": "No write permission for the specified download path"}), 400

    scraper = MusicScraper()

    def generate():
        try:
            for event in scraper.scrape_playlist(spotify_playlist_link, download_path):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'event': 'error', 'data': {'message': str(e)}})}\n\n"

    return Response(generate(), mimetype='text/event-stream')

@app.route('/api/download/<path:filename>')
def download_file(filename):
    return send_from_directory(directory=request.args.get('path', ''), filename=filename, as_attachment=True)


# Lambda handler for AWS
def lambda_handler(event, context):
    handler = Mangum(app)
    return handler(event, context)


if __name__ == '__main__':
    app.run()
