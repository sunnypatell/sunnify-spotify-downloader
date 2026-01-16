"""Flask backend for Sunnify web client.

Lightweight API that fetches Spotify metadata without downloading.
Optimized for free-tier hosting (512MB RAM, 0.1 CPU).

For actual MP3 downloads, use the desktop app.
"""

from __future__ import annotations

import gc
import os
import sys
from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS

# Add parent directory to path for spotifydown_api import
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from spotifydown_api import (  # noqa: E402
    PlaylistClient,
    SpotifyDownAPIError,
    SpotifyEmbedAPI,
    detect_spotify_url_type,
)

app = Flask(__name__)
CORS(app)

# Reusable client (saves memory on repeated requests)
_playlist_client: PlaylistClient | None = None


def get_playlist_client() -> PlaylistClient:
    """Get or create a playlist client (singleton pattern for memory efficiency)."""
    global _playlist_client
    if _playlist_client is None:
        _playlist_client = PlaylistClient()
    return _playlist_client


@app.route("/api/scrape-playlist", methods=["POST"])
def scrape_playlist():
    """Fetch Spotify playlist/track metadata (no downloads).

    This endpoint is optimized for free-tier hosting:
    - No file downloads (saves CPU/memory/disk)
    - No yt-dlp/FFmpeg processing
    - Just returns metadata for the frontend to display

    Request body:
        {"playlistUrl": "https://open.spotify.com/playlist/..."}

    Response:
        {"event": "complete", "data": {"playlistName": "...", "tracks": [...]}}
    """
    try:
        data = request.get_json()
        spotify_url = data.get("playlistUrl", "").strip()

        if not spotify_url:
            return jsonify({"event": "error", "data": {"message": "No URL provided"}}), 400

        # Detect URL type
        url_type, item_id = detect_spotify_url_type(spotify_url)

        if url_type == "unknown" or not item_id:
            return (
                jsonify({"event": "error", "data": {"message": "Invalid Spotify URL"}}),
                400,
            )

        client = get_playlist_client()
        tracks: list[dict] = []

        if url_type == "track":
            # Single track
            api = SpotifyEmbedAPI()
            track = api.get_track(item_id)
            tracks.append(
                {
                    "id": track.spotify_id,
                    "title": track.title,
                    "artists": track.artists,
                    "album": track.album or "",
                    "cover": track.cover_url or "",
                    "releaseDate": track.release_date or "",
                    "downloadLink": "",  # No server-side downloads
                }
            )
            playlist_name = f"{track.title} - {track.artists}"

        else:
            # Playlist
            metadata = client.get_playlist_metadata(item_id)
            playlist_name = f"{metadata.name} - {metadata.owner or 'Unknown'}"

            # Fetch tracks with memory-efficient iteration
            for track in client.iter_playlist_tracks(item_id):
                tracks.append(
                    {
                        "id": track.spotify_id,
                        "title": track.title,
                        "artists": track.artists,
                        "album": track.album or "",
                        "cover": track.cover_url or "",
                        "releaseDate": track.release_date or "",
                        "downloadLink": "",  # No server-side downloads
                    }
                )

                # Memory management for large playlists
                if len(tracks) % 50 == 0:
                    gc.collect()

        # Final cleanup
        gc.collect()

        return jsonify(
            {
                "event": "complete",
                "data": {
                    "playlistName": playlist_name,
                    "tracks": tracks,
                },
            }
        )

    except SpotifyDownAPIError as e:
        return jsonify({"event": "error", "data": {"message": f"Spotify API error: {e}"}}), 500
    except Exception as e:
        return jsonify({"event": "error", "data": {"message": f"Error: {e}"}}), 500


@app.route("/api/health")
def health_check():
    """Health check endpoint for monitoring."""
    return jsonify({"status": "ok", "mode": "metadata-only"})


@app.route("/")
def index():
    """Root endpoint with API info."""
    return jsonify(
        {
            "name": "Sunnify API",
            "version": "2.0.0",
            "mode": "metadata-only",
            "description": "Fetches Spotify metadata. For MP3 downloads, use the desktop app.",
            "endpoints": {
                "POST /api/scrape-playlist": "Fetch playlist/track metadata",
                "GET /api/health": "Health check",
            },
        }
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
