"""Utility script that probes Spotify embed endpoint and yt-dlp."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from yt_dlp import YoutubeDL

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from spotifydown_api import (  # noqa: E402
    PlaylistClient,
    SpotifyDownAPIError,
    SpotifyEmbedAPI,
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


def check_embed_api(
    api: SpotifyEmbedAPI, playlist_id: str
) -> tuple[EndpointResult, TrackInfo | None]:
    """Check the Spotify embed page API."""
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
        return (
            EndpointResult(
                name="spotify_embed_api",
                url=f"https://open.spotify.com/embed/playlist/{playlist_id}",
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
                name="spotify_embed_api",
                url=f"https://open.spotify.com/embed/playlist/{playlist_id}",
                method="GET",
                ok=False,
                status_code=None,
                notes=str(exc),
            ),
            None,
        )


def check_playlist_client(
    client: PlaylistClient,
    playlist_id: str,
) -> tuple[EndpointResult, TrackInfo | None]:
    """Check the high-level PlaylistClient."""
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
                name="playlist_client",
                url=f"PlaylistClient for {playlist_id}",
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
                name="playlist_client",
                url=f"PlaylistClient for {playlist_id}",
                method="GET",
                ok=False,
                status_code=None,
                notes=str(exc),
            ),
            None,
        )


def check_youtube_search(query: str) -> EndpointResult:
    """Check if yt-dlp YouTube search works."""
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


def check_youtube_download(track: TrackInfo) -> EndpointResult:
    """Check if yt-dlp can find audio for a track."""
    query = f"{track.title} {track.artists} audio"
    search = f"ytsearch1:{query}"
    try:
        with YoutubeDL({"quiet": True}) as ydl:
            info = ydl.extract_info(search, download=False)
            if info.get("entries"):
                info = info["entries"][0]
            title = info.get("title", "<unknown title>")
            url = info.get("webpage_url", "<unknown url>")
            notes = f"Track '{track.title}' resolved to: {title} ({url})"
            return EndpointResult(
                name="youtube_track_search",
                url=search,
                method="yt-dlp",
                ok=True,
                status_code=None,
                notes=notes,
            )
    except Exception as exc:  # pragma: no cover - diagnostic script
        return EndpointResult(
            name="youtube_track_search",
            url=search,
            method="yt-dlp",
            ok=False,
            status_code=None,
            notes=str(exc),
        )


def main() -> int:
    playlist_id = "37i9dQZF1DXcBWIGoYBM5M"  # Spotify's "Today's Top Hits"
    query = "Rick Astley Never Gonna Give You Up"

    embed_api = SpotifyEmbedAPI()
    playlist_client = PlaylistClient()

    results: list[EndpointResult] = []

    # Check embed API (primary method)
    embed_result, first_track = check_embed_api(embed_api, playlist_id)
    results.append(embed_result)

    # Check PlaylistClient (high-level wrapper)
    client_result, _ = check_playlist_client(playlist_client, playlist_id)
    results.append(client_result)

    # Check YouTube search (fallback for audio)
    results.append(check_youtube_search(query))

    # Check YouTube can find a specific track
    if first_track is not None:
        results.append(check_youtube_download(first_track))

    # Print summary
    print("\n" + "=" * 60)
    print("API STATUS SUMMARY")
    print("=" * 60)
    for result in results:
        status = "✓ OK" if result.ok else "✗ FAILED"
        print(f"\n{result.name}: {status}")
        print(f"  URL: {result.url}")
        print(f"  Notes: {result.notes[:100]}...")
    print("\n" + "=" * 60)

    # Output JSON
    print("\nJSON Output:")
    json.dump([result.as_dict() for result in results], sys.stdout, indent=2)
    sys.stdout.write("\n")

    # Return non-zero if any critical checks failed
    critical_checks = ["spotify_embed_api", "youtube_search"]
    failed_critical = [r for r in results if r.name in critical_checks and not r.ok]
    return 1 if failed_critical else 0


if __name__ == "__main__":  # pragma: no cover - manual diagnostic
    raise SystemExit(main())
