"""Flask backend for Sunnify web client.

Lightweight API that fetches Spotify metadata without downloading.
Optimized for free-tier hosting (512MB RAM, 0.1 CPU).

For actual MP3 downloads, use the desktop app.

Hardening, all configurable through the environment:
- CORS answers only the web client's origins (SUNNIFY_CORS_ORIGINS)
- request bodies are capped (a URL fits in far less than 16 KB)
- each client IP gets SUNNIFY_RATE_LIMIT scrapes a minute; a scrape fans out
  into one Spotify request per track, so an unmetered endpoint would let anyone
  aim this server at Spotify
- a playlist returns at most SUNNIFY_MAX_TRACKS tracks, flagged as truncated
- every response says no-sniff, no-framing, no-referrer and no-cache
"""

from __future__ import annotations

import gc
import os
import sys
import threading
import time
from collections import deque
from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

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

VERSION = "3.0.0"
DEFAULT_ORIGINS = "https://sunnify-spotify-downloader.vercel.app,http://localhost:3000"
MAX_BODY_BYTES = 16 * 1024


def _env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.environ.get(name, "")))
    except ValueError:
        return default


ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get("SUNNIFY_CORS_ORIGINS", DEFAULT_ORIGINS).split(",")
    if o.strip()
]
RATE_LIMIT_PER_MINUTE = _env_int("SUNNIFY_RATE_LIMIT", 20)
MAX_TRACKS = _env_int("SUNNIFY_MAX_TRACKS", 1000)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_BODY_BYTES
# Render (and any host like it) terminates TLS at one proxy that appends the
# client to X-Forwarded-For; trusting exactly that one hop gives the real IP
# for rate limiting without letting a client spoof it with its own header.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)  # type: ignore[method-assign]
CORS(app, origins=ALLOWED_ORIGINS, methods=["GET", "POST", "OPTIONS"])

# Reusable client (saves memory on repeated requests)
_playlist_client: PlaylistClient | None = None


def get_playlist_client() -> PlaylistClient:
    """Get or create a playlist client (singleton pattern for memory efficiency)."""
    global _playlist_client
    if _playlist_client is None:
        _playlist_client = PlaylistClient()
    return _playlist_client


class RateLimiter:
    """Sliding one-minute window per client key; in-process, which fits one free instance."""

    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> tuple[bool, int]:
        """(allowed, seconds until a slot frees)."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] >= 60:
                hits.popleft()
            if len(hits) >= self.per_minute:
                return False, max(1, int(60 - (now - hits[0])) + 1)
            hits.append(now)
            # forget idle clients so the table can't grow without bound
            if len(self._hits) > 10_000:
                for stale in [k for k, v in self._hits.items() if not v or now - v[-1] >= 60]:
                    del self._hits[stale]
            return True, 0

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = RateLimiter(RATE_LIMIT_PER_MINUTE)


def _error(message: str, status: int, **headers):
    response = jsonify({"event": "error", "data": {"message": message}})
    response.status_code = status
    response.headers.update(headers)
    return response


@app.after_request
def security_headers(response):
    """A JSON API never needs to be framed, sniffed, cached or to send a referrer."""
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault(
        "Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"
    )
    response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.errorhandler(HTTPException)
def http_error(exc: HTTPException):
    """Werkzeug's errors (404, 405, 413, ...) in the API's own JSON envelope."""
    return _error(exc.description or exc.name, exc.code or 500)


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
        {"event": "complete", "data": {"playlistName": "...", "tracks": [...], "truncated": false}}
    """
    allowed, retry_after = limiter.allow(request.remote_addr or "unknown")
    if not allowed:
        return _error(
            "Too many requests - try again in a minute", 429, **{"Retry-After": str(retry_after)}
        )
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return _error("Invalid request body", 400)

        spotify_url = data.get("playlistUrl")
        if not isinstance(spotify_url, str) or not spotify_url.strip():
            return _error("No URL provided", 400)
        spotify_url = spotify_url.strip()

        # Detect URL type
        url_type, item_id = detect_spotify_url_type(spotify_url)

        if url_type == "unknown" or not item_id:
            return _error("Invalid Spotify URL", 400)

        client = get_playlist_client()
        tracks: list[dict] = []
        truncated = False

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
            # Playlist or album (album reuses the same embed-parsing path).
            metadata = client.get_playlist_metadata(item_id, content_type=url_type)
            playlist_name = f"{metadata.name} - {metadata.owner or 'Unknown'}"
            playlist_cover = metadata.cover_url or ""

            # Fetch tracks with memory-efficient iteration
            for track in client.iter_playlist_tracks(item_id, content_type=url_type):
                if len(tracks) >= MAX_TRACKS:
                    truncated = True
                    break
                # Use track cover if available, otherwise fall back to playlist cover
                cover = track.cover_url or playlist_cover
                tracks.append(
                    {
                        "id": track.spotify_id,
                        "title": track.title,
                        "artists": track.artists,
                        "album": track.album or "",
                        "cover": cover,
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
                    "truncated": truncated,
                },
            }
        )

    except HTTPException:
        # werkzeug's own (413 body too large, ...) go to http_error, not the 500 path
        raise
    except ValueError:
        # bad/unsupported spotify url is client input error, not a server fault
        return _error("Invalid Spotify URL", 400)
    except SpotifyDownAPIError:
        # log the detail server-side; don't leak exception internals to the client
        app.logger.exception("spotify api error during scrape")
        return _error("Spotify API error", 500)
    except Exception:
        app.logger.exception("unexpected error during scrape")
        return _error("Internal server error", 500)


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
            "version": VERSION,
            "mode": "metadata-only",
            "description": "Fetches Spotify metadata. For MP3 downloads, use the desktop app.",
            "endpoints": {
                "POST /api/scrape-playlist": "Fetch playlist/track metadata",
                "GET /api/health": "Health check",
            },
        }
    )


if __name__ == "__main__":
    # the dev server: local only unless HOST says otherwise (production runs gunicorn)
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    app.run(host=host, port=port, debug=False)
