"""Flask backend for Sunnify web client.

Uses SpotifyEmbedAPI for playlist data and yt-dlp for audio downloads.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import requests
from flask import Flask, Response, jsonify, request, send_from_directory
from flask_cors import CORS
from mutagen.easyid3 import EasyID3
from mutagen.id3 import APIC, ID3
from yt_dlp import YoutubeDL

# Add parent directory to path for spotifydown_api import
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from spotifydown_api import (  # noqa: E402
    PlaylistClient,
    SpotifyDownAPIError,
    extract_playlist_id,
    sanitize_filename,
)

app = Flask(__name__)
CORS(app)


class MusicScraper:
    """Scraper that uses Spotify embed API and yt-dlp for downloads."""

    def __init__(self):
        self.session = requests.Session()
        self.playlist_client = PlaylistClient()

    def scrape_playlist(self, spotify_playlist_link: str, music_folder: str):
        """Scrape a Spotify playlist and download tracks via YouTube."""
        try:
            playlist_id = self._extract_playlist_id(spotify_playlist_link)
            metadata = self.playlist_client.get_playlist_metadata(playlist_id)

            # sanitize folder name
            folder_name = "".join(
                c
                for c in f"{metadata.name} - {metadata.owner or 'Unknown'}"
                if c.isalnum() or c in [" ", "_", "-"]
            )
            playlist_folder_path = os.path.join(music_folder, folder_name)

            if not os.path.exists(playlist_folder_path):
                os.makedirs(playlist_folder_path)

            downloaded_tracks: list[dict] = []
            total_tracks = metadata.track_count or 100  # estimate if unknown

            for idx, track in enumerate(self.playlist_client.iter_playlist_tracks(playlist_id)):
                filename = self._sanitize_filename(f"{track.title} - {track.artists}.mp3")
                filepath = os.path.join(playlist_folder_path, filename)

                try:
                    # download via youtube search
                    search_query = f"ytsearch1:{track.title} {track.artists} audio"
                    self._download_audio(search_query, filepath)

                    # write metadata
                    self._write_metadata(filepath, track)

                    downloaded_tracks.append(
                        {
                            "id": track.spotify_id,
                            "title": track.title,
                            "artists": track.artists,
                            "album": track.album,
                            "cover": track.cover_url,
                            "downloadLink": f"/api/download/{filename}",
                        }
                    )

                    yield {
                        "event": "progress",
                        "data": {
                            "progress": (idx + 1) / total_tracks * 100,
                            "currentTrack": {
                                "title": track.title,
                                "artists": track.artists,
                            },
                        },
                    }

                except Exception as error:
                    print(f"[*] Error downloading '{track.title}': {error}")
                    yield {
                        "event": "error",
                        "data": {"message": f"Error downloading {track.title}: {error}"},
                    }

            yield {
                "event": "complete",
                "data": {
                    "playlistName": f"{metadata.name} - {metadata.owner or 'Unknown'}",
                    "tracks": downloaded_tracks,
                },
            }

        except SpotifyDownAPIError as e:
            yield {
                "event": "error",
                "data": {"message": f"Spotify API error: {e}"},
            }
        except Exception as e:
            yield {
                "event": "error",
                "data": {"message": f"An error occurred: {e}"},
            }

    def _download_audio(self, search_query: str, output_path: str) -> None:
        """Download audio using yt-dlp."""
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": output_path.replace(".mp3", ".%(ext)s"),
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
            "quiet": True,
            "no_warnings": True,
        }

        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([search_query])

    def _write_metadata(self, filepath: str, track) -> None:
        """Write ID3 metadata to the downloaded file."""
        try:
            # wait for file to exist (yt-dlp postprocessor creates it)
            if not os.path.exists(filepath):
                return

            audio = EasyID3(filepath)
            audio["title"] = track.title
            audio["artist"] = track.artists
            audio["album"] = track.album or "Unknown Album"
            audio.save()

            # embed cover art if available
            if track.cover_url:
                cover_response = self.session.get(track.cover_url, timeout=10)
                if cover_response.status_code == 200:
                    audio = ID3(filepath)
                    audio["APIC"] = APIC(
                        encoding=3,
                        mime="image/jpeg",
                        type=3,
                        desc="Cover",
                        data=cover_response.content,
                    )
                    audio.save()

        except Exception as e:
            print(f"Error writing metadata for {filepath}: {e}")

    def _extract_playlist_id(self, link: str) -> str:
        """Extract playlist ID from Spotify URL."""
        return extract_playlist_id(link)

    def _sanitize_filename(self, filename: str) -> str:
        """Remove invalid characters from filename."""
        return sanitize_filename(filename, allow_spaces=True)


@app.route("/api/scrape-playlist", methods=["POST"])
def scrape_playlist():
    """Endpoint to scrape a Spotify playlist."""
    data = request.get_json()
    spotify_playlist_link = data.get("playlistUrl")
    download_path = data.get("downloadPath", tempfile.gettempdir())

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

    return Response(generate(), mimetype="text/event-stream")


@app.route("/api/download/<path:filename>")
def download_file(filename):
    """Endpoint to download a file."""
    return send_from_directory(
        directory=request.args.get("path", ""),
        path=filename,
        as_attachment=True,
    )


@app.route("/api/health")
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
