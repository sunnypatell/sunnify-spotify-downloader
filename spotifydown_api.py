"""Spotify playlist data fetcher using the embed endpoint.

The original spotifydown mirrors are dead. This module now uses Spotify's
embed page which returns playlist data in the __NEXT_DATA__ JSON blob.
Audio is downloaded via yt-dlp YouTube search as the fallback.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass

import requests

_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


class SpotifyDownAPIError(RuntimeError):
    """Raised when Spotify data cannot be fetched."""


@dataclass
class PlaylistInfo:
    name: str
    owner: str | None
    description: str | None
    cover_url: str | None
    track_count: int | None = None


@dataclass
class TrackInfo:
    id: str
    title: str
    artists: str
    album: str | None
    release_date: str | None
    cover_url: str | None
    duration_ms: int | None
    preview_url: str | None
    raw: dict[str, object]


class SpotifyEmbedAPI:
    """Fetch playlist data from Spotify's embed page.

    The embed page (https://open.spotify.com/embed/playlist/{id}) contains
    full track data in a __NEXT_DATA__ JSON blob, including:
    - Track titles, artists, durations
    - Track URIs/IDs
    - 96kbps audio preview URLs
    - Anonymous access tokens

    This works without any authentication.
    """

    _EMBED_URL = "https://open.spotify.com/embed/playlist/{playlist_id}"
    _NEXT_DATA_PATTERN = re.compile(r'<script id="__NEXT_DATA__"[^>]*>([^<]+)</script>')

    def __init__(self, *, session: requests.Session | None = None) -> None:
        self._session = session or requests.Session()

    def _headers(self) -> dict[str, str]:
        return {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "accept-language": "en-US,en;q=0.9",
            "user-agent": _DEFAULT_USER_AGENT,
        }

    def _fetch_embed_data(self, playlist_id: str) -> dict:
        """Fetch and parse the embed page __NEXT_DATA__."""
        url = self._EMBED_URL.format(playlist_id=playlist_id)

        try:
            response = self._session.get(url, headers=self._headers(), timeout=30)
        except requests.RequestException as exc:
            raise SpotifyDownAPIError(f"Failed to fetch embed page: {exc}") from exc

        if response.status_code != 200:
            raise SpotifyDownAPIError(f"Embed page returned HTTP {response.status_code}")

        # Extract __NEXT_DATA__ JSON from HTML
        match = self._NEXT_DATA_PATTERN.search(response.text)
        if not match:
            raise SpotifyDownAPIError("Could not find __NEXT_DATA__ in embed page")

        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError as exc:
            raise SpotifyDownAPIError(f"Invalid JSON in __NEXT_DATA__: {exc}") from exc

        return data

    def _extract_entity(self, data: dict) -> dict:
        """Extract the entity data from __NEXT_DATA__."""
        try:
            return data["props"]["pageProps"]["state"]["data"]["entity"]
        except (KeyError, TypeError) as exc:
            raise SpotifyDownAPIError(f"Unexpected embed page structure: {exc}") from exc

    def get_playlist_metadata(self, playlist_id: str) -> PlaylistInfo:
        """Get playlist metadata from the embed page."""
        data = self._fetch_embed_data(playlist_id)
        entity = self._extract_entity(data)

        name = entity.get("name") or entity.get("title") or "Unknown Playlist"
        subtitle = entity.get("subtitle")  # Usually "Spotify" for official playlists

        # Get cover URL from coverArt sources
        cover_url = None
        cover_art = entity.get("coverArt", {})
        sources = cover_art.get("sources", [])
        if sources:
            # Get the largest image
            cover_url = sources[-1].get("url") if sources else None

        # Get track count from trackList
        track_list = entity.get("trackList", [])
        track_count = len(track_list) if isinstance(track_list, list) else None

        return PlaylistInfo(
            name=str(name),
            owner=str(subtitle) if subtitle else None,
            description=None,  # Embed page doesn't include description
            cover_url=cover_url,
            track_count=track_count,
        )

    def iter_playlist_tracks(self, playlist_id: str) -> Iterator[TrackInfo]:
        """Iterate over playlist tracks from the embed page.

        Note: The embed page only returns the first ~50 tracks.
        For larger playlists, this may be incomplete.
        """
        data = self._fetch_embed_data(playlist_id)
        entity = self._extract_entity(data)

        track_list = entity.get("trackList", [])

        for track in track_list:
            if not isinstance(track, dict):
                continue

            # Extract track ID from URI (spotify:track:XXXXX)
            uri = track.get("uri", "")
            track_id = uri.split(":")[-1] if uri.startswith("spotify:track:") else ""
            if not track_id:
                continue

            title = track.get("title", "Unknown Track")
            artists = track.get("subtitle", "")  # Artist name is in subtitle

            # Get preview URL if available
            preview_url = None
            audio_preview = track.get("audioPreview", {})
            if isinstance(audio_preview, dict):
                preview_url = audio_preview.get("url")

            duration_ms = track.get("duration")

            yield TrackInfo(
                id=track_id,
                title=str(title),
                artists=str(artists),
                album=None,  # Embed page doesn't include album name
                release_date=None,  # Embed page doesn't include release date
                cover_url=None,  # Individual track covers not in embed
                duration_ms=int(duration_ms) if duration_ms else None,
                preview_url=preview_url,
                raw=dict(track),
            )


# Legacy class kept for compatibility - redirects to embed API
class SpotifyDownAPI:
    """Legacy wrapper - spotifydown mirrors are dead.

    This class is kept for API compatibility but now raises errors
    since all spotifydown endpoints are non-functional.
    """

    def __init__(self, **kwargs) -> None:
        pass

    def get_playlist_metadata(self, playlist_id: str) -> PlaylistInfo:
        raise SpotifyDownAPIError(
            "spotifydown mirrors are no longer functional. Use SpotifyEmbedAPI instead."
        )

    def iter_playlist_tracks(self, playlist_id: str) -> Iterator[TrackInfo]:
        raise SpotifyDownAPIError(
            "spotifydown mirrors are no longer functional. Use SpotifyEmbedAPI instead."
        )

    def get_track_download_link(self, track_id: str) -> str | None:
        raise SpotifyDownAPIError(
            "spotifydown mirrors are no longer functional. "
            "Use yt-dlp YouTube search for audio downloads."
        )

    def get_track_youtube_id(self, track_id: str) -> str | None:
        raise SpotifyDownAPIError(
            "spotifydown mirrors are no longer functional. "
            "Use yt-dlp YouTube search for audio downloads."
        )


# Legacy class kept for compatibility - token endpoint is blocked
class SpotifyPublicAPI:
    """Legacy wrapper - Spotify's anonymous token endpoint is blocked.

    This class is kept for API compatibility but now raises errors
    since the /get_access_token endpoint returns 403.
    """

    def __init__(self, **kwargs) -> None:
        pass

    def get_playlist_metadata(self, playlist_id: str) -> PlaylistInfo:
        raise SpotifyDownAPIError(
            "Spotify's anonymous token endpoint is blocked. Use SpotifyEmbedAPI instead."
        )

    def iter_playlist_tracks(self, playlist_id: str) -> Iterator[TrackInfo]:
        raise SpotifyDownAPIError(
            "Spotify's anonymous token endpoint is blocked. Use SpotifyEmbedAPI instead."
        )


class PlaylistClient:
    """High-level client for fetching Spotify playlist data.

    Uses the embed page API as the primary (and only working) method.
    """

    def __init__(
        self,
        *,
        session: requests.Session | None = None,
        base_urls: Sequence[str] | None = None,  # Ignored - kept for compatibility
    ) -> None:
        self._session = session or requests.Session()
        self._embed_api = SpotifyEmbedAPI(session=self._session)

    def get_playlist_metadata(self, playlist_id: str) -> PlaylistInfo:
        """Get playlist metadata."""
        return self._embed_api.get_playlist_metadata(playlist_id)

    def iter_playlist_tracks(self, playlist_id: str) -> Iterator[TrackInfo]:
        """Iterate over playlist tracks.

        Note: The embed page may only return the first ~50 tracks.
        """
        yield from self._embed_api.iter_playlist_tracks(playlist_id)

    def get_track_download_link(self, track_id: str) -> str | None:
        """No longer available - spotifydown is dead.

        Use yt-dlp YouTube search instead.
        """
        return None

    def get_track_youtube_id(self, track_id: str) -> str | None:
        """No longer available - spotifydown is dead.

        Use yt-dlp YouTube search instead.
        """
        return None


# Utility functions shared across desktop app and web backend


def extract_playlist_id(url: str) -> str:
    """Extract playlist ID from a Spotify URL.

    Args:
        url: Spotify playlist URL like https://open.spotify.com/playlist/ABC123

    Returns:
        The playlist ID (e.g., "ABC123")

    Raises:
        ValueError: If the URL is not a valid Spotify playlist URL
    """
    pattern = r"https://open\.spotify\.com/playlist/([a-zA-Z0-9]+)"
    match = re.match(pattern, url)
    if not match:
        raise ValueError("Invalid Spotify playlist URL.")
    return match.group(1)


def sanitize_filename(name: str, allow_spaces: bool = True) -> str:
    """Sanitize a string for use as a filename.

    Args:
        name: The string to sanitize
        allow_spaces: Whether to allow spaces in the result

    Returns:
        A sanitized string safe for use as a filename
    """
    valid_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.")
    if allow_spaces:
        valid_chars.add(" ")
    sanitized = "".join(c for c in name if c in valid_chars)
    # Collapse multiple spaces and strip
    sanitized = " ".join(sanitized.split())
    return sanitized or "Unknown"


__all__ = [
    "PlaylistClient",
    "PlaylistInfo",
    "SpotifyDownAPI",
    "SpotifyDownAPIError",
    "SpotifyEmbedAPI",
    "SpotifyPublicAPI",
    "TrackInfo",
    "extract_playlist_id",
    "sanitize_filename",
]
