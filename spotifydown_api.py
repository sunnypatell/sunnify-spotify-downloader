"""Lightweight wrapper around third-party spotifydown-style endpoints."""

from __future__ import annotations

import os
import time
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass

import requests

_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)


class SpotifyDownAPIError(RuntimeError):
    """Raised when none of the configured SpotifyDown endpoints respond."""


@dataclass
class PlaylistInfo:
    name: str
    owner: str | None
    description: str | None
    cover_url: str | None


@dataclass
class TrackInfo:
    id: str
    title: str
    artists: str
    album: str | None
    release_date: str | None
    cover_url: str | None
    raw: dict[str, object]


_DEFAULT_BASE_URLS: Sequence[str] = (
    "https://api.spotifydown.com",
    "https://api.spotifydown.org",
    "https://api.spotifydown.net",
    "https://spotimate.io/api",
)


def _load_base_urls() -> list[str]:
    env_value = os.getenv("SPOTIFYDOWN_BASE_URLS")
    if env_value:
        urls = [entry.strip() for entry in env_value.split(",") if entry.strip()]
        if urls:
            return urls
    return list(_DEFAULT_BASE_URLS)


class SpotifyDownAPI:
    """Thin wrapper around the undocumented spotifydown endpoints."""

    def __init__(
        self, *, session: requests.Session | None = None, base_urls: Sequence[str] | None = None
    ) -> None:
        self._session = session or requests.Session()
        self._base_urls = list(base_urls) if base_urls else _load_base_urls()
        if not self._base_urls:
            raise ValueError("At least one SpotifyDown base URL must be configured.")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _headers(self) -> dict[str, str]:
        return {
            "accept": "application/json",
            "origin": "https://spotifydown.com",
            "referer": "https://spotifydown.com/",
            "user-agent": _DEFAULT_USER_AGENT,
        }

    def _request_json(
        self, path: str, *, params: dict[str, object] | None = None
    ) -> dict[str, object]:
        errors: list[str] = []
        for base in self._base_urls:
            url = f"{base.rstrip('/')}/{path.lstrip('/')}"
            try:
                response = self._session.get(
                    url, headers=self._headers(), params=params, timeout=20
                )
            except (
                requests.RequestException
            ) as exc:  # pragma: no cover - network failures are environment specific
                errors.append(f"{base}: {exc}")
                continue
            if response.status_code == 200:
                try:
                    return response.json()
                except ValueError as exc:
                    errors.append(f"{base}: invalid JSON ({exc})")
                    continue
            errors.append(f"{base}: HTTP {response.status_code}")
        raise SpotifyDownAPIError("; ".join(errors))

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------
    def get_playlist_metadata(self, playlist_id: str) -> PlaylistInfo:
        payload = self._request_json(f"metadata/playlist/{playlist_id}")
        return PlaylistInfo(
            name=str(payload.get("title", "Unknown Playlist")),
            owner=str(payload.get("artists", "")).strip() or None,
            description=str(payload.get("description", "")).strip() or None,
            cover_url=str(payload.get("cover", "")).strip() or None,
        )

    def iter_playlist_tracks(self, playlist_id: str) -> Iterator[TrackInfo]:
        next_offset: int | None = 0
        while next_offset is not None:
            params = {"offset": next_offset} if next_offset else None
            payload = self._request_json(f"trackList/playlist/{playlist_id}", params=params)
            tracks: Iterable[dict[str, object]] = payload.get("trackList", [])  # type: ignore[assignment]
            for entry in tracks:
                track_id = str(entry.get("id", ""))
                if not track_id:
                    continue
                title = str(entry.get("title", "Unknown Track"))
                artists = str(entry.get("artists", ""))
                album = entry.get("album")
                release = entry.get("releaseDate")
                cover = entry.get("cover") or entry.get("image")
                yield TrackInfo(
                    id=track_id,
                    title=title,
                    artists=artists,
                    album=str(album) if album else None,
                    release_date=str(release) if release else None,
                    cover_url=str(cover) if cover else None,
                    raw=dict(entry),
                )
            next_offset = payload.get("nextOffset")  # type: ignore[assignment]

    def get_track_download_link(self, track_id: str) -> str | None:
        payload = self._request_json(f"download/{track_id}")
        link = payload.get("link")
        return str(link) if link else None

    def get_track_youtube_id(self, track_id: str) -> str | None:
        payload = self._request_json(f"getId/{track_id}")
        youtube_id = payload.get("id")
        return str(youtube_id) if youtube_id else None


class SpotifyPublicAPI:
    """Fetch playlist data from Spotify's public web endpoints."""

    _TOKEN_URL = "https://open.spotify.com/get_access_token"
    _API_BASE = "https://api.spotify.com/v1"

    def __init__(self, *, session: requests.Session | None = None) -> None:
        self._session = session or requests.Session()
        self._access_token: str | None = None
        self._expiry_epoch: float = 0.0

    def _token_headers(self) -> dict[str, str]:
        return {
            "accept": "application/json",
            "accept-language": "en-US,en;q=0.9",
            "user-agent": _DEFAULT_USER_AGENT,
        }

    def _refresh_access_token(self) -> str:
        params = {"reason": "transport", "productType": "web_player"}
        try:
            response = self._session.get(
                self._TOKEN_URL,
                headers=self._token_headers(),
                params=params,
                timeout=15,
            )
        except (
            requests.RequestException
        ) as exc:  # pragma: no cover - network failures are host specific
            raise SpotifyDownAPIError(f"spotify access token request failed: {exc}") from exc

        if response.status_code != 200:
            snippet = response.text[:120].replace("\n", " ")
            raise SpotifyDownAPIError(
                f"spotify access token request failed: HTTP {response.status_code}: {snippet}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise SpotifyDownAPIError(f"spotify access token response invalid JSON: {exc}") from exc

        token = payload.get("accessToken")
        if not token:
            raise SpotifyDownAPIError("spotify access token response missing 'accessToken'")

        expires_at_ms = payload.get("accessTokenExpirationTimestampMs")
        if isinstance(expires_at_ms, (int, float)):
            self._expiry_epoch = float(expires_at_ms) / 1000.0
        else:
            expires_in = payload.get("expiresIn") or 3600
            self._expiry_epoch = time.time() + float(expires_in)

        self._access_token = str(token)
        return self._access_token

    def _ensure_access_token(self) -> str:
        if self._access_token and time.time() < self._expiry_epoch - 30:
            return self._access_token
        return self._refresh_access_token()

    def _api_headers(self) -> dict[str, str]:
        return {
            "accept": "application/json",
            "content-type": "application/json",
            "user-agent": _DEFAULT_USER_AGENT,
            "authorization": f"Bearer {self._ensure_access_token()}",
        }

    def _api_get(self, path: str, *, params: dict[str, object] | None = None) -> dict[str, object]:
        url = path if path.startswith("http") else f"{self._API_BASE}/{path.lstrip('/')}"
        last_error: Exception | None = None
        for attempt in range(2):
            headers = self._api_headers()
            try:
                response = self._session.get(url, headers=headers, params=params, timeout=20)
            except (
                requests.RequestException
            ) as exc:  # pragma: no cover - network failures are host specific
                last_error = exc
                break

            if response.status_code == 401 and attempt == 0:
                # Token expired, clear and retry once.
                self._access_token = None
                self._expiry_epoch = 0.0
                continue

            if response.status_code == 429:
                retry_after = response.headers.get("retry-after")
                try:
                    sleep_seconds = min(float(retry_after), 5.0) if retry_after else 1.0
                except ValueError:
                    sleep_seconds = 1.0
                time.sleep(
                    sleep_seconds
                )  # pragma: no cover - rate limiting is environment dependent
                continue

            if response.status_code != 200:
                snippet = response.text[:120].replace("\n", " ")
                raise SpotifyDownAPIError(
                    f"spotify playlist request failed: HTTP {response.status_code}: {snippet}"
                )

            try:
                return response.json()
            except ValueError as exc:
                raise SpotifyDownAPIError(f"spotify playlist response invalid JSON: {exc}") from exc

        if last_error:
            raise SpotifyDownAPIError(
                f"spotify playlist request failed: {last_error}"
            ) from last_error
        raise SpotifyDownAPIError("spotify playlist request failed: unknown error")

    def get_playlist_metadata(self, playlist_id: str) -> PlaylistInfo:
        payload = self._api_get(f"playlists/{playlist_id}")
        images: Iterable[dict[str, object]] = payload.get("images", [])  # type: ignore[assignment]
        cover_url = None
        for image in images:
            if isinstance(image, dict) and image.get("url"):
                cover_url = str(image["url"])
                break

        owner = payload.get("owner") or {}
        owner_name = None
        if isinstance(owner, dict):
            owner_name = owner.get("display_name") or owner.get("id")

        description = payload.get("description")
        if isinstance(description, str) and not description.strip():
            description = None

        return PlaylistInfo(
            name=str(payload.get("name", "Unknown Playlist")),
            owner=str(owner_name).strip() if owner_name else None,
            description=str(description).strip() if description else None,
            cover_url=cover_url,
        )

    def iter_playlist_tracks(self, playlist_id: str) -> Iterator[TrackInfo]:
        next_path: str | None = f"playlists/{playlist_id}/tracks"
        while next_path:
            payload = self._api_get(next_path, params={"limit": 100})
            items: Iterable[dict[str, object]] = payload.get("items", [])  # type: ignore[assignment]
            for item in items:
                track_info = item.get("track")
                if not isinstance(track_info, dict):
                    continue
                track_id = track_info.get("id")
                if not track_id:
                    continue
                if track_info.get("type") not in {None, "track"}:
                    continue

                artists_field = track_info.get("artists", [])
                if isinstance(artists_field, list):
                    artists = ", ".join(
                        str(artist.get("name", "")).strip()
                        for artist in artists_field
                        if isinstance(artist, dict)
                    )
                else:
                    artists = ""

                album = track_info.get("album") or {}
                album_name = None
                release_date = None
                cover_url = None
                if isinstance(album, dict):
                    album_name = album.get("name")
                    release_date = album.get("release_date")
                    album_images = album.get("images") or []
                    if isinstance(album_images, list):
                        for image in album_images:
                            if isinstance(image, dict) and image.get("url"):
                                cover_url = str(image["url"])
                                break

                yield TrackInfo(
                    id=str(track_id),
                    title=str(track_info.get("name", "Unknown Track")),
                    artists=artists,
                    album=str(album_name) if album_name else None,
                    release_date=str(release_date) if release_date else None,
                    cover_url=cover_url,
                    raw=dict(track_info),
                )

            next_path = payload.get("next")  # type: ignore[assignment]
            if next_path:
                next_path = str(next_path)


class PlaylistClient:
    """High-level helper that falls back across Spotify web and spotifydown."""

    def __init__(
        self,
        *,
        session: requests.Session | None = None,
        base_urls: Sequence[str] | None = None,
    ) -> None:
        self._session = session or requests.Session()
        self._providers: list[tuple[str, object]] = [
            ("spotify_web", SpotifyPublicAPI(session=self._session)),
            ("spotifydown", SpotifyDownAPI(session=self._session, base_urls=base_urls)),
        ]

    def _call_first(self, method: str, *args):
        errors: list[str] = []
        for name, provider in self._providers:
            handler = getattr(provider, method)
            try:
                return handler(*args)
            except SpotifyDownAPIError as exc:
                errors.append(f"{name}: {exc}")
        raise SpotifyDownAPIError("; ".join(errors) if errors else "no providers configured")

    def get_playlist_metadata(self, playlist_id: str) -> PlaylistInfo:
        return self._call_first("get_playlist_metadata", playlist_id)

    def iter_playlist_tracks(self, playlist_id: str) -> Iterator[TrackInfo]:
        errors: list[str] = []
        for name, provider in self._providers:
            handler = provider.iter_playlist_tracks
            try:
                yield from handler(playlist_id)
                return
            except SpotifyDownAPIError as exc:
                errors.append(f"{name}: {exc}")
        raise SpotifyDownAPIError("; ".join(errors) if errors else "no providers configured")

    def get_track_download_link(self, track_id: str) -> str | None:
        for name, provider in self._providers:
            if isinstance(provider, SpotifyDownAPI):
                try:
                    return provider.get_track_download_link(track_id)
                except SpotifyDownAPIError as exc:
                    raise SpotifyDownAPIError(f"{name}: {exc}") from exc
        raise SpotifyDownAPIError("no spotifydown providers configured")

    def get_track_youtube_id(self, track_id: str) -> str | None:
        for name, provider in self._providers:
            if isinstance(provider, SpotifyDownAPI):
                try:
                    return provider.get_track_youtube_id(track_id)
                except SpotifyDownAPIError as exc:
                    raise SpotifyDownAPIError(f"{name}: {exc}") from exc
        raise SpotifyDownAPIError("no spotifydown providers configured")


__all__ = [
    "PlaylistClient",
    "PlaylistInfo",
    "SpotifyDownAPI",
    "SpotifyDownAPIError",
    "SpotifyPublicAPI",
    "TrackInfo",
]
