"""Utility script that probes all Spotify endpoints and yt-dlp.

Tests:
1. Embed page API (primary) - /embed/playlist/{id}
2. spclient API (fallback for large playlists)
3. oEmbed API (quick validation)
4. Track-page album scrape (og:description via facebookexternalhit UA, v2.0.9)
5. YouTube raw reachability via yt-dlp (ytsearch1)
6. YouTube real download selector (ytsearch5 + MusicScraper._select_youtube_match,
   i.e. the actual title/artist/duration matching the app uses since v2.0.9)
"""

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

# Import the real download selector so the YouTube check exercises the same
# path the app does (ytsearch5 + title/artist/duration filter), not a stale
# ytsearch1 top-hit. Bare instance avoids spinning up the QThread/Qt stack.
from Spotify_Downloader import MusicScraper  # noqa: E402
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


def check_youtube_match(track: TrackInfo) -> EndpointResult:
    """Check the REAL download selector: ytsearch5 + _select_youtube_match.

    This is what the app actually runs since v2.0.9 (title + artist + duration
    filtering), so it's the meaningful "can we still resolve audio" signal -
    unlike a bare ytsearch1 top-hit, which can pass while the real selector
    rejects everything (or vice versa).
    """
    search = f"ytsearch5:{track.title} {track.artists} audio"
    # Bare instance: skip QThread.__init__ (no Qt), the selector only needs the
    # class's static/class methods + duration constants.
    matcher = MusicScraper.__new__(MusicScraper)
    duration_s = (track.duration_ms / 1000) if track.duration_ms else None
    try:
        url = matcher._select_youtube_match(
            search,
            duration_s,
            expected_title=track.title,
            expected_artists=track.artists,
        )
        if url:
            return EndpointResult(
                name="youtube_match_selector",
                url=search,
                method="yt-dlp",
                ok=True,
                status_code=None,
                notes=f"Track '{track.title}' matched by real selector -> {url}",
            )
        return EndpointResult(
            name="youtube_match_selector",
            url=search,
            method="yt-dlp",
            ok=False,
            status_code=None,
            notes=(
                f"Track '{track.title}' returned no match from _select_youtube_match "
                "(title/artist/duration filter rejected all candidates)"
            ),
        )
    except Exception as exc:  # pragma: no cover - diagnostic script
        return EndpointResult(
            name="youtube_match_selector",
            url=search,
            method="yt-dlp",
            ok=False,
            status_code=None,
            notes=str(exc),
        )


def check_track_album_scrape(api: SpotifyEmbedAPI, track_id: str) -> EndpointResult:
    """Check the v2.0.9 album scrape: og:description on the track page via the
    facebookexternalhit UA. This is a live external dependency now (single-track
    downloads get their album tag from here), so it earns its own probe."""
    url = f"https://open.spotify.com/track/{track_id}"
    try:
        album = api._fetch_track_album_from_page(track_id)
        if album:
            return EndpointResult(
                name="track_album_scrape",
                url=url,
                method="GET",
                ok=True,
                status_code=200,
                notes=f"Album resolved from og:description: {album}",
            )
        return EndpointResult(
            name="track_album_scrape",
            url=url,
            method="GET",
            ok=False,
            status_code=None,
            notes="No album in og:description (Spotify may have changed the track page HTML)",
        )
    except Exception as exc:  # pragma: no cover - diagnostic script
        return EndpointResult(
            name="track_album_scrape",
            url=url,
            method="GET",
            ok=False,
            status_code=None,
            notes=str(exc),
        )


def check_large_playlist_fallback(client: PlaylistClient, playlist_id: str) -> EndpointResult:
    """Check that large playlists work with spclient fallback."""
    try:
        metadata = client.get_playlist_metadata(playlist_id)
        track_count = 0
        for _ in client.iter_playlist_tracks(playlist_id):
            track_count += 1
        notes = f"Retrieved all {track_count} tracks (expected {metadata.track_count})"
        return EndpointResult(
            name="large_playlist_fallback",
            url=f"spclient + individual embeds for {playlist_id}",
            method="GET",
            ok=track_count >= 100,
            status_code=200,
            notes=notes,
        )
    except Exception as exc:
        return EndpointResult(
            name="large_playlist_fallback",
            url=f"spclient fallback for {playlist_id}",
            method="GET",
            ok=False,
            status_code=None,
            notes=str(exc),
        )


def check_oembed_validation(client: PlaylistClient, playlist_id: str) -> EndpointResult:
    """Check the oEmbed validation endpoint."""
    try:
        is_valid = client.validate_playlist(playlist_id)
        return EndpointResult(
            name="oembed_validation",
            url=f"https://open.spotify.com/oembed?url=...{playlist_id}",
            method="GET",
            ok=is_valid,
            status_code=200 if is_valid else None,
            notes="Playlist validation successful" if is_valid else "Validation failed",
        )
    except Exception as exc:
        return EndpointResult(
            name="oembed_validation",
            url=f"oEmbed for {playlist_id}",
            method="GET",
            ok=False,
            status_code=None,
            notes=str(exc),
        )


def main() -> int:
    playlist_id = "37i9dQZF1DXcBWIGoYBM5M"  # Spotify's "Today's Top Hits"
    large_playlist_id = "37i9dQZF1DX5Ejj0EkURtP"  # "All Out 2010s" - 150 tracks
    query = "Rick Astley Never Gonna Give You Up"
    album_probe_track_id = "4PTG3Z6ehGkBFwjybzWkR8"  # "Never Gonna Give You Up"

    embed_api = SpotifyEmbedAPI()
    playlist_client = PlaylistClient()

    results: list[EndpointResult] = []

    # Check embed API (primary method)
    embed_result, first_track = check_embed_api(embed_api, playlist_id)
    results.append(embed_result)

    # Check PlaylistClient (high-level wrapper)
    client_result, _ = check_playlist_client(playlist_client, playlist_id)
    results.append(client_result)

    # Check oEmbed validation
    results.append(check_oembed_validation(playlist_client, playlist_id))

    # Check large playlist fallback (spclient + individual embeds)
    results.append(check_large_playlist_fallback(playlist_client, large_playlist_id))

    # Check the track-page album scrape (v2.0.9 og:description path)
    results.append(check_track_album_scrape(embed_api, album_probe_track_id))

    # Check YouTube raw reachability (does search respond at all)
    results.append(check_youtube_search(query))

    # Check the REAL download selector (ytsearch5 + _select_youtube_match)
    if first_track is not None:
        results.append(check_youtube_match(first_track))

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
