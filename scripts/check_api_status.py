"""Utility script that probes spotifydown-style endpoints and yt-dlp."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from yt_dlp import YoutubeDL

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from spotifydown_api import (  # noqa: E402
    PlaylistClient,
    SpotifyDownAPI,
    SpotifyDownAPIError,
    SpotifyPublicAPI,
    TrackInfo,
)


@dataclass
class EndpointResult:
    name: str
    url: str
    method: str
    ok: bool
    status_code: int | None
    notes: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "url": self.url,
            "method": self.method,
            "ok": self.ok,
            "status_code": self.status_code,
            "notes": self.notes,
        }


def summarize_playlist(
    metadata_title: str,
    metadata_owner: str | None,
    track_titles: list[str],
) -> str:
    owner_text = f" by {metadata_owner}" if metadata_owner else ""
    sample_text = ", ".join(track_titles or ["<no tracks returned>"])
    return f"Playlist '{metadata_title}'{owner_text}. Sample tracks: {sample_text}"


def check_playlist_client(
    client: PlaylistClient,
    playlist_id: str,
) -> tuple[EndpointResult, TrackInfo | None]:
    try:
        metadata = client.get_playlist_metadata(playlist_id)
        sample_tracks: list[str] = []
        first_track: TrackInfo | None = None
        for track in client.iter_playlist_tracks(playlist_id):
            if first_track is None:
                first_track = track
            sample_tracks.append(track.title)
            if len(sample_tracks) >= 3:
                break
        notes = summarize_playlist(metadata.name, metadata.owner, sample_tracks)
        return (
            EndpointResult(
                name="playlist_client_lookup",
                url=f"combined providers for {playlist_id}",
                method="GET",
                ok=True,
                status_code=200,
                notes=notes,
            ),
            first_track,
        )
    except SpotifyDownAPIError as exc:
        return (
            EndpointResult(
                name="playlist_client_lookup",
                url=f"combined providers for {playlist_id}",
                method="GET",
                ok=False,
                status_code=None,
                notes=str(exc),
            ),
            None,
        )


def check_spotify_public_playlist(api: SpotifyPublicAPI, playlist_id: str) -> EndpointResult:
    try:
        metadata = api.get_playlist_metadata(playlist_id)
        sample_tracks: list[str] = []
        for track in api.iter_playlist_tracks(playlist_id):
            sample_tracks.append(track.title)
            if len(sample_tracks) >= 3:
                break
        notes = summarize_playlist(metadata.name, metadata.owner, sample_tracks)
        return EndpointResult(
            name="spotify_web_playlist_lookup",
            url=f"https://api.spotify.com/v1/playlists/{playlist_id}",
            method="GET",
            ok=True,
            status_code=200,
            notes=notes,
        )
    except SpotifyDownAPIError as exc:
        return EndpointResult(
            name="spotify_web_playlist_lookup",
            url=f"https://api.spotify.com/v1/playlists/{playlist_id}",
            method="GET",
            ok=False,
            status_code=None,
            notes=str(exc),
        )


def check_spotifydown_playlist(
    api: SpotifyDownAPI, playlist_id: str
) -> tuple[EndpointResult, TrackInfo | None]:
    try:
        metadata = api.get_playlist_metadata(playlist_id)
        sample_tracks: list[str] = []
        first_track: TrackInfo | None = None
        for track in api.iter_playlist_tracks(playlist_id):
            if first_track is None:
                first_track = track
            sample_tracks.append(track.title)
            if len(sample_tracks) >= 3:
                break
        notes = summarize_playlist(metadata.name, metadata.owner, sample_tracks)
        result = EndpointResult(
            name="spotifydown_playlist_lookup",
            url=f"trackList/playlist/{playlist_id}",
            method="GET",
            ok=True,
            status_code=200,
            notes=notes,
        )
        return result, first_track
    except SpotifyDownAPIError as exc:
        return (
            EndpointResult(
                name="spotifydown_playlist_lookup",
                url=f"trackList/playlist/{playlist_id}",
                method="GET",
                ok=False,
                status_code=None,
                notes=str(exc),
            ),
            None,
        )


def check_spotifydown_download(api: SpotifyDownAPI, track: TrackInfo) -> EndpointResult:
    try:
        link = api.get_track_download_link(track.id)
        if not link:
            raise SpotifyDownAPIError("Download link missing from response")
        notes = f"Resolved {track.title} to {link[:80]}..."
        return EndpointResult(
            name="spotifydown_track_download",
            url=f"download/{track.id}",
            method="GET",
            ok=True,
            status_code=200,
            notes=notes,
        )
    except SpotifyDownAPIError as exc:
        return EndpointResult(
            name="spotifydown_track_download",
            url=f"download/{track.id}",
            method="GET",
            ok=False,
            status_code=None,
            notes=str(exc),
        )


def check_youtube_search(query: str) -> EndpointResult:
    search = f"ytsearch1:{query}"
    try:
        with YoutubeDL({"quiet": True}) as ydl:
            info = ydl.extract_info(search, download=False)
            if info.get("entries"):
                info = info["entries"][0]
            title = info.get("title", "<unknown title>")
            url = info.get("webpage_url", "<unknown url>")
            notes = f"Resolved '{query}' to {title} ({url})"
            return EndpointResult(
                name="youtube_search",
                url=search,
                method="yt-dlp",
                ok=True,
                status_code=None,
                notes=notes,
            )
    except Exception as exc:  # pragma: no cover - diagnostic script
        return EndpointResult(
            name="youtube_search",
            url=search,
            method="yt-dlp",
            ok=False,
            status_code=None,
            notes=str(exc),
        )


def main() -> int:
    playlist_id = "37i9dQZF1DXcBWIGoYBM5M"  # Spotify's "Today's Top Hits"
    query = "Rick Astley Never Gonna Give You Up"

    session = requests.Session()
    playlist_client = PlaylistClient(session=session)
    web_api = SpotifyPublicAPI(session=session)
    spotifydown_api = SpotifyDownAPI(session=session)

    client_result, first_track = check_playlist_client(playlist_client, playlist_id)
    results = [
        client_result,
        check_spotify_public_playlist(web_api, playlist_id),
    ]

    down_result, _ = check_spotifydown_playlist(spotifydown_api, playlist_id)
    results.append(down_result)

    results.append(check_youtube_search(query))
    if first_track is not None:
        results.append(check_spotifydown_download(spotifydown_api, first_track))

    json.dump([result.as_dict() for result in results], sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":  # pragma: no cover - manual diagnostic
    raise SystemExit(main())
