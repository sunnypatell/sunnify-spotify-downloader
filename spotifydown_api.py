"""Spotify playlist data fetcher with multiple fallback endpoints.

Primary: Embed page (/embed/playlist/{id}) - returns up to 100 tracks
Fallback: spclient API - returns full track URIs for large playlists
Individual: Track embed pages - for metadata on tracks beyond 100

All methods work without authentication by extracting anonymous tokens
from Spotify's embed pages.
"""

from __future__ import annotations

import functools
import json
import re
import time
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

import requests

T = TypeVar("T")

_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


class SpotifyDownAPIError(RuntimeError):
    """Raised when Spotify data cannot be fetched."""


class NetworkError(SpotifyDownAPIError):
    """Network/connectivity issues - typically retryable."""


class ExtractionError(SpotifyDownAPIError):
    """Failed to extract data from response - usually not retryable."""


class RateLimitError(SpotifyDownAPIError):
    """Rate limited by Spotify - should back off before retrying."""


def retry_on_network_error(
    max_attempts: int = 3,
    backoff_factor: float = 1.0,
    exceptions: tuple = (NetworkError, requests.Timeout, requests.ConnectionError),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to retry a function on network errors with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts before giving up
        backoff_factor: Multiplier for wait time between attempts (wait = backoff_factor * 2^attempt)
        exceptions: Tuple of exception types to catch and retry
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        wait_time = backoff_factor * (2**attempt)
                        time.sleep(wait_time)
            raise last_exception  # type: ignore

        return wrapper

    return decorator


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

    @property
    def spotify_id(self) -> str:
        """Alias for id field for compatibility."""
        return self.id


class SpotifyEmbedAPI:
    """Fetch playlist data from Spotify's embed page.

    The embed page (https://open.spotify.com/embed/playlist/{id}) contains
    full track data in a __NEXT_DATA__ JSON blob, including:
    - Track titles, artists, durations
    - Track URIs/IDs
    - 96kbps audio preview URLs
    - Anonymous access tokens (can be used with spclient API)

    This works without any authentication.
    Limitation: Returns max ~100 tracks per playlist.
    """

    _EMBED_PLAYLIST_URL = "https://open.spotify.com/embed/playlist/{playlist_id}"
    _EMBED_TRACK_URL = "https://open.spotify.com/embed/track/{track_id}"
    _OEMBED_URL = "https://open.spotify.com/oembed"
    _SPCLIENT_URL = "https://spclient.wg.spotify.com/playlist/v2/playlist/{playlist_id}"
    _NEXT_DATA_PATTERN = re.compile(r'<script id="__NEXT_DATA__"[^>]*>([^<]+)</script>')

    def __init__(self, *, session: requests.Session | None = None) -> None:
        self._session = session or requests.Session()
        self._cached_token: str | None = None
        self._token_expiry: float = 0

    @staticmethod
    def _deep_find(data: dict, key: str, max_depth: int = 6) -> dict | None:
        """Recursively search for a dict containing the given key."""
        if not isinstance(data, dict) or max_depth <= 0:
            return None
        if key in data:
            return data
        for v in data.values():
            if isinstance(v, dict):
                result = SpotifyEmbedAPI._deep_find(v, key, max_depth - 1)
                if result is not None:
                    return result
        return None

    @staticmethod
    def _resolve_path(data: dict, path: tuple[str, ...]) -> Any:
        """Traverse nested dicts along a key path, returning None on failure."""
        result: Any = data
        for key in path:
            if not isinstance(result, dict):
                return None
            result = result.get(key)
        return result

    def _headers(self) -> dict[str, str]:
        return {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "accept-language": "en-US,en;q=0.9",
            "user-agent": _DEFAULT_USER_AGENT,
        }

    @retry_on_network_error(max_attempts=3, backoff_factor=1.0)
    def _fetch_embed_data(self, url: str) -> dict:
        """Fetch and parse __NEXT_DATA__ from any embed page.

        Raises:
            NetworkError: For connection issues (retryable)
            RateLimitError: When rate limited by Spotify (retryable with backoff)
            ExtractionError: When page structure is unexpected (not retryable)
        """
        try:
            response = self._session.get(url, headers=self._headers(), timeout=30)
        except (requests.Timeout, requests.ConnectionError) as exc:
            raise NetworkError(f"Network error fetching embed page: {exc}") from exc
        except requests.RequestException as exc:
            raise SpotifyDownAPIError(f"Failed to fetch embed page: {exc}") from exc

        if response.status_code == 429:
            raise RateLimitError("Rate limited by Spotify - please wait before retrying")
        if response.status_code in (401, 403):
            raise ExtractionError(
                f"Access denied (HTTP {response.status_code}) - playlist may be private"
            )
        if response.status_code != 200:
            raise NetworkError(f"Embed page returned HTTP {response.status_code}")

        match = self._NEXT_DATA_PATTERN.search(response.text)
        if not match:
            raise ExtractionError("Could not find __NEXT_DATA__ in embed page")

        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError as exc:
            raise ExtractionError(f"Invalid JSON in __NEXT_DATA__: {exc}") from exc

        # Cache the access token if present (try multiple paths)
        _TOKEN_PATHS = (
            ("props", "pageProps", "state", "settings", "session"),
            ("props", "pageProps", "settings", "session"),
            ("props", "pageProps", "session"),
        )
        for path in _TOKEN_PATHS:
            session_data = self._resolve_path(data, path)
            if isinstance(session_data, dict) and "accessToken" in session_data:
                self._cached_token = session_data.get("accessToken")
                expiry_ms = session_data.get("accessTokenExpirationTimestampMs", 0)
                self._token_expiry = expiry_ms / 1000 if expiry_ms else 0
                break

        return data

    _ENTITY_PATHS = (
        ("props", "pageProps", "state", "data", "entity"),
        ("props", "pageProps", "data", "entity"),
        ("props", "pageProps", "entity"),
    )

    def _extract_entity(self, data: dict) -> dict:
        """Extract the entity data from __NEXT_DATA__.

        Tries multiple known paths first, then falls back to recursive
        search for dicts containing 'trackList' or a known entity 'type'.
        This handles Spotify A/B testing different page structures.
        """
        for path in self._ENTITY_PATHS:
            result = self._resolve_path(data, path)
            if isinstance(result, dict):
                return result

        # Fallback: recursive search for entity-like dict
        container = self._deep_find(data, "trackList")
        if isinstance(container, dict) and "trackList" in container:
            return container
        container = self._deep_find(data, "type")
        if isinstance(container, dict) and container.get("type") in ("playlist", "track"):
            return container

        page_props = self._resolve_path(data, ("props", "pageProps")) or {}
        available_keys = list(page_props.keys())[:10] if isinstance(page_props, dict) else []
        raise ExtractionError(
            f"Could not find entity in embed page. pageProps keys: {available_keys}"
        )

    def _get_access_token(self, playlist_id: str) -> str | None:
        """Get a valid access token, refreshing if needed."""
        if self._cached_token and time.time() < self._token_expiry - 60:
            return self._cached_token

        # Fetch embed page to get fresh token
        url = self._EMBED_PLAYLIST_URL.format(playlist_id=playlist_id)
        self._fetch_embed_data(url)
        return self._cached_token

    def get_playlist_metadata(self, playlist_id: str) -> PlaylistInfo:
        """Get playlist metadata from the embed page."""
        url = self._EMBED_PLAYLIST_URL.format(playlist_id=playlist_id)
        data = self._fetch_embed_data(url)
        entity = self._extract_entity(data)

        name = entity.get("name") or entity.get("title") or "Unknown Playlist"
        subtitle = entity.get("subtitle")

        # Get cover URL from coverArt sources
        cover_url = None
        cover_art = entity.get("coverArt", {})
        sources = cover_art.get("sources", [])
        if sources:
            cover_url = sources[-1].get("url")

        # Get track count - try spclient for accurate count
        track_list = entity.get("trackList", [])
        track_count = len(track_list)

        # Try to get true count from spclient
        try:
            token = self._cached_token
            if token:
                spclient_url = self._SPCLIENT_URL.format(playlist_id=playlist_id)
                headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
                resp = self._session.get(spclient_url, headers=headers, timeout=10)
                if resp.status_code == 200:
                    spc_data = resp.json()
                    track_count = spc_data.get("length", track_count)
        except Exception:
            pass  # Fall back to embed count

        return PlaylistInfo(
            name=str(name),
            owner=str(subtitle) if subtitle else None,
            description=entity.get("description"),
            cover_url=cover_url,
            track_count=track_count,
        )

    def iter_playlist_tracks(self, playlist_id: str) -> Iterator[TrackInfo]:
        """Iterate over playlist tracks with fallback for large playlists.

        For playlists with <=100 tracks: Uses embed page (fast).
        For playlists with >100 tracks: Uses spclient for URIs + individual
        track embeds for metadata on remaining tracks.
        """
        url = self._EMBED_PLAYLIST_URL.format(playlist_id=playlist_id)
        data = self._fetch_embed_data(url)
        entity = self._extract_entity(data)

        track_list = entity.get("trackList", [])
        embed_track_ids: set[str] = set()

        # Yield tracks from embed page (up to ~100)
        for track in track_list:
            if not isinstance(track, dict):
                continue

            uri = track.get("uri", "")
            track_id = uri.split(":")[-1] if uri.startswith("spotify:track:") else ""
            if not track_id:
                continue

            embed_track_ids.add(track_id)
            yield self._parse_track(track, track_id)

        # Check if there are more tracks via spclient
        token = self._cached_token
        if not token:
            return

        try:
            spclient_url = self._SPCLIENT_URL.format(playlist_id=playlist_id)
            headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
            resp = self._session.get(spclient_url, headers=headers, timeout=30)

            if resp.status_code != 200:
                return

            spc_data = resp.json()
            total_tracks = spc_data.get("length", 0)

            if total_tracks <= len(embed_track_ids):
                return  # All tracks already yielded

            # Get remaining track URIs from spclient
            contents = spc_data.get("contents", {})
            items = contents.get("items", [])

            for item in items:
                uri = item.get("uri", "")
                if not uri.startswith("spotify:track:"):
                    continue

                track_id = uri.split(":")[-1]
                if track_id in embed_track_ids:
                    continue  # Already yielded

                # Fetch individual track metadata
                try:
                    track_info = self._fetch_track_metadata(track_id)
                    if track_info:
                        yield track_info
                except Exception:
                    # If individual fetch fails, yield minimal info
                    yield TrackInfo(
                        id=track_id,
                        title=f"Track {track_id}",
                        artists="Unknown Artist",
                        album=None,
                        release_date=None,
                        cover_url=None,
                        duration_ms=None,
                        preview_url=None,
                        raw={"uri": uri},
                    )

        except Exception:
            pass  # spclient fallback failed, just return what we have

    def _parse_track(self, track: dict, track_id: str) -> TrackInfo:
        """Parse a track dict from embed trackList."""
        title = track.get("title") or track.get("name") or "Unknown Track"
        artists = track.get("subtitle") or track.get("artists") or ""

        if isinstance(artists, list):
            artists = ", ".join(a.get("name", "") for a in artists if isinstance(a, dict))

        preview_url = None
        audio_preview = track.get("audioPreview", {})
        if isinstance(audio_preview, dict):
            preview_url = audio_preview.get("url")

        duration_ms = track.get("duration")

        return TrackInfo(
            id=track_id,
            title=str(title),
            artists=str(artists),
            album=track.get("album", {}).get("name")
            if isinstance(track.get("album"), dict)
            else None,
            release_date=track.get("releaseDate"),
            cover_url=None,
            duration_ms=int(duration_ms) if duration_ms else None,
            preview_url=preview_url,
            raw=dict(track),
        )

    def _fetch_track_metadata(self, track_id: str) -> TrackInfo | None:
        """Fetch metadata for a single track from its embed page."""
        url = self._EMBED_TRACK_URL.format(track_id=track_id)

        try:
            data = self._fetch_embed_data(url)
            entity = self._extract_entity(data)
        except SpotifyDownAPIError:
            return None

        title = entity.get("name") or entity.get("title") or "Unknown Track"

        # Artists can be in different formats
        artists_data = entity.get("artists", [])
        if isinstance(artists_data, list):
            artists = ", ".join(a.get("name", "") for a in artists_data if isinstance(a, dict))
        else:
            artists = entity.get("subtitle", "")

        preview_url = None
        audio_preview = entity.get("audioPreview", {})
        if isinstance(audio_preview, dict):
            preview_url = audio_preview.get("url")

        # Extract cover URL from visualIdentity.image
        cover_url = None
        visual_identity = entity.get("visualIdentity", {})
        images = visual_identity.get("image", [])
        if images:
            # Get the largest image (usually last or highest resolution)
            for img in images:
                if isinstance(img, dict) and img.get("url"):
                    cover_url = img.get("url")
                    if img.get("maxWidth", 0) >= 300:
                        break  # Use 300px+ image

        # Extract release date properly
        release_date = None
        rd = entity.get("releaseDate")
        if isinstance(rd, dict):
            release_date = rd.get("isoString", "")[:10]  # YYYY-MM-DD
        elif isinstance(rd, str):
            release_date = rd

        # Try to get album name
        album = None
        # Album info might be in relatedEntityUri or other fields
        # For now, we'll leave it None as individual track embeds don't include album

        return TrackInfo(
            id=track_id,
            title=str(title),
            artists=str(artists),
            album=album,
            release_date=release_date,
            cover_url=cover_url,
            duration_ms=entity.get("duration"),
            preview_url=preview_url,
            raw=dict(entity),
        )

    def validate_playlist(self, playlist_id: str) -> bool:
        """Quick validation using oEmbed API (no full data fetch)."""
        try:
            params = {"url": f"https://open.spotify.com/playlist/{playlist_id}"}
            resp = self._session.get(self._OEMBED_URL, params=params, timeout=10)
            return resp.status_code == 200
        except Exception:
            return False

    def get_track(self, track_id: str) -> TrackInfo:
        """Get metadata for a single track.

        Args:
            track_id: Spotify track ID

        Returns:
            TrackInfo with track metadata

        Raises:
            SpotifyDownAPIError: If track cannot be fetched
        """
        track_info = self._fetch_track_metadata(track_id)
        if track_info is None:
            raise SpotifyDownAPIError(f"Could not fetch track {track_id}")
        return track_info


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

    Uses multiple fallback methods:
    1. Embed page API (primary) - fast, up to 100 tracks
    2. spclient API - for full track list on large playlists
    3. Individual track embeds - for metadata on tracks beyond 100
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
        """Iterate over all playlist tracks.

        For large playlists (>100 tracks), automatically uses fallback
        methods to retrieve complete track list.
        """
        yield from self._embed_api.iter_playlist_tracks(playlist_id)

    def validate_playlist(self, playlist_id: str) -> bool:
        """Quick validation that a playlist exists."""
        return self._embed_api.validate_playlist(playlist_id)

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

    def get_track(self, track_id: str) -> TrackInfo:
        """Get metadata for a single track.

        Args:
            track_id: Spotify track ID

        Returns:
            TrackInfo with track metadata
        """
        return self._embed_api.get_track(track_id)


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


def extract_track_id(url: str) -> str:
    """Extract track ID from a Spotify URL.

    Args:
        url: Spotify track URL like https://open.spotify.com/track/ABC123

    Returns:
        The track ID (e.g., "ABC123")

    Raises:
        ValueError: If the URL is not a valid Spotify track URL
    """
    pattern = r"https://open\.spotify\.com/track/([a-zA-Z0-9]+)"
    match = re.match(pattern, url)
    if not match:
        raise ValueError("Invalid Spotify track URL.")
    return match.group(1)


def detect_spotify_url_type(url: str) -> tuple[str, str]:
    """Detect the type of Spotify URL and extract the ID.

    Args:
        url: Spotify URL (track or playlist)

    Returns:
        Tuple of (type, id) where type is 'track' or 'playlist'

    Raises:
        ValueError: If the URL is not a valid Spotify URL
    """
    # Try playlist first
    playlist_pattern = r"https://open\.spotify\.com/playlist/([a-zA-Z0-9]+)"
    match = re.match(playlist_pattern, url)
    if match:
        return ("playlist", match.group(1))

    # Try track
    track_pattern = r"https://open\.spotify\.com/track/([a-zA-Z0-9]+)"
    match = re.match(track_pattern, url)
    if match:
        return ("track", match.group(1))

    raise ValueError("Invalid Spotify URL. Must be a track or playlist URL.")


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
    "ExtractionError",
    "NetworkError",
    "PlaylistClient",
    "PlaylistInfo",
    "RateLimitError",
    "SpotifyDownAPI",
    "SpotifyDownAPIError",
    "SpotifyEmbedAPI",
    "SpotifyPublicAPI",
    "TrackInfo",
    "detect_spotify_url_type",
    "extract_playlist_id",
    "extract_track_id",
    "sanitize_filename",
]
