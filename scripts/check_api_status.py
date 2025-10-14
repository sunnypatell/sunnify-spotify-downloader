"""Utility script that probes spotifydown-style endpoints and yt-dlp."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Any, Dict, Optional

from yt_dlp import YoutubeDL

from spotifydown_api import SpotifyDownAPI, SpotifyDownAPIError, TrackInfo


@dataclass
class EndpointResult:
    name: str
    url: str
    method: str
    ok: bool
    status_code: Optional[int]
    notes: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "url": self.url,
            "method": self.method,
            "ok": self.ok,
            "status_code": self.status_code,
            "notes": self.notes,
        }


def check_spotifydown_playlist(api: SpotifyDownAPI, playlist_id: str) -> tuple[EndpointResult, Optional[TrackInfo]]:
    try:
        metadata = api.get_playlist_metadata(playlist_id)
        sample_tracks: list[str] = []
        first_track: Optional[TrackInfo] = None
        for track in api.iter_playlist_tracks(playlist_id):
            if first_track is None:
                first_track = track
            sample_tracks.append(track.title)
            if len(sample_tracks) >= 3:
                break
        if not sample_tracks:
            sample_tracks.append("<no tracks returned>")
        notes = (
            f"Playlist '{metadata.name}'"
            + (f" by {metadata.owner}" if metadata.owner else "")
            + f". Sample tracks: {', '.join(sample_tracks)}"
        )
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

    api = SpotifyDownAPI()
    playlist_result, first_track = check_spotifydown_playlist(api, playlist_id)
    results = [playlist_result, check_youtube_search(query)]
    if first_track is not None:
        results.append(check_spotifydown_download(api, first_track))

    json.dump([result.as_dict() for result in results], sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":  # pragma: no cover - manual diagnostic
    raise SystemExit(main())
