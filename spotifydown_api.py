"""Lightweight wrapper around third-party spotifydown-style endpoints."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Iterable, Iterator, List, Optional, Sequence

import requests


class SpotifyDownAPIError(RuntimeError):
    """Raised when none of the configured SpotifyDown endpoints respond."""


@dataclass
class PlaylistInfo:
    name: str
    owner: Optional[str]
    description: Optional[str]
    cover_url: Optional[str]


@dataclass
class TrackInfo:
    id: str
    title: str
    artists: str
    album: Optional[str]
    release_date: Optional[str]
    cover_url: Optional[str]
    raw: Dict[str, object]


_DEFAULT_BASE_URLS: Sequence[str] = (
    "https://api.spotifydown.com",
    "https://api.spotifydown.org",
    "https://api.spotifydown.net",
    "https://spotimate.io/api",
)


def _load_base_urls() -> List[str]:
    env_value = os.getenv("SPOTIFYDOWN_BASE_URLS")
    if env_value:
        urls = [entry.strip() for entry in env_value.split(",") if entry.strip()]
        if urls:
            return urls
    return list(_DEFAULT_BASE_URLS)


class SpotifyDownAPI:
    """Thin wrapper around the undocumented spotifydown endpoints."""

    def __init__(self, *, session: Optional[requests.Session] = None, base_urls: Optional[Sequence[str]] = None) -> None:
        self._session = session or requests.Session()
        self._base_urls = list(base_urls) if base_urls else _load_base_urls()
        if not self._base_urls:
            raise ValueError("At least one SpotifyDown base URL must be configured.")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _headers(self) -> Dict[str, str]:
        return {
            "accept": "application/json",
            "origin": "https://spotifydown.com",
            "referer": "https://spotifydown.com/",
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
        }

    def _request_json(self, path: str, *, params: Optional[Dict[str, object]] = None) -> Dict[str, object]:
        errors: List[str] = []
        for base in self._base_urls:
            url = f"{base.rstrip('/')}/{path.lstrip('/')}"
            try:
                response = self._session.get(url, headers=self._headers(), params=params, timeout=20)
            except requests.RequestException as exc:  # pragma: no cover - network failures are environment specific
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
        next_offset: Optional[int] = 0
        while next_offset is not None:
            params = {"offset": next_offset} if next_offset else None
            payload = self._request_json(f"trackList/playlist/{playlist_id}", params=params)
            tracks: Iterable[Dict[str, object]] = payload.get("trackList", [])  # type: ignore[assignment]
            for entry in tracks:
                track_id = str(entry.get("id", ""))
                if not track_id:
                    continue
                title = str(entry.get("title", "Unknown Track"))
                artists = str(entry.get("artists", ""))
                album = entry.get("album")
                release = entry.get("releaseDate")
                cover = entry.get("cover" ) or entry.get("image" )
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

    def get_track_download_link(self, track_id: str) -> Optional[str]:
        payload = self._request_json(f"download/{track_id}")
        link = payload.get("link")
        return str(link) if link else None

    def get_track_youtube_id(self, track_id: str) -> Optional[str]:
        payload = self._request_json(f"getId/{track_id}")
        youtube_id = payload.get("id")
        return str(youtube_id) if youtube_id else None


__all__ = [
    "PlaylistInfo",
    "SpotifyDownAPI",
    "SpotifyDownAPIError",
    "TrackInfo",
]
