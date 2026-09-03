"""Utility script that probes all Spotify endpoints and yt-dlp.

Tests:
1. Embed page API (primary) - /embed/playlist/{id}
2. spclient API (fallback for large playlists)
3. oEmbed API (quick validation)
4. Track-page album scrape (og:description via facebookexternalhit UA, v2.0.9)
5. YouTube raw reachability via yt-dlp (ytsearch1)
6. YouTube real download selector (ytsearch5 + MusicScraper._select_youtube_match,
   i.e. the actual title/artist/duration matching the app uses since v2.0.9)
7. A real end-to-end download through MusicScraper's own code path, which
   reports itself skipped when YouTube bot-gates the IP (CI runners are
   datacenter addresses and are gated; run locally for real coverage) (v2.4.1)
8. The retry client set still names clients yt-dlp ships (v2.4.1)
9. Spotify's unavailable-page shape still tells itself apart from content,
   so the region/private error message keeps firing correctly (v2.4.1)

Checks 7-9 exist because each of them broke silently once: they fail loudly
here instead of turning into a user's bug report.
"""

from __future__ import annotations

import contextlib
import json
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

if sys.platform == "win32":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            with contextlib.suppress(Exception):
                stream.reconfigure(encoding="utf-8", errors="replace")

from yt_dlp import YoutubeDL

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Import the real download selector so the YouTube check exercises the same
# path the app does (ytsearch5 + title/artist/duration filter), not a stale
# ytsearch1 top-hit. Bare instance avoids spinning up the QThread/Qt stack.
from Spotify_Downloader import MusicScraper, _retry_player_clients  # noqa: E402
from spotifydown_api import (  # noqa: E402
    ContentUnavailableError,
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


def check_real_download(scraper: MusicScraper, query: str, expected_title: str) -> EndpointResult:
    """Download a track through the app's own code, end to end.

    Deliberately calls MusicScraper.download_track_audio rather than
    reimplementing the strategy: the checker cannot drift from the app if
    it runs the app. That covers search, the title/artist/duration
    selector, the default client attempt, the retry client set, and the
    FFmpeg postprocessing in one result.

    Individual attempts failing is normal and is the whole reason a retry
    exists - YouTube 403s the default path on some videos from some IPs.
    Only "no audio at all" is a real alarm, so only that fails this check.
    """
    with tempfile.TemporaryDirectory() as tmp:
        destination = str(Path(tmp) / "probe.mp3")
        try:
            landed = scraper.download_track_audio(query, destination, expected_title=expected_title)
        except Exception as exc:
            # YouTube gates datacenter IPs, which is what CI runners are, so
            # this check is usually blocked there. That is the environment
            # refusing us, not Sunnify breaking, and failing on it daily
            # would train everyone to ignore this job. Any other cause is a
            # real alarm and still fails.
            if scraper._network_blocked:
                return EndpointResult(
                    "youtube_real_download",
                    query,
                    "MusicScraper",
                    True,
                    None,
                    "SKIPPED: YouTube is bot-gating this IP, so a real download "
                    "cannot be attempted from here. The other YouTube checks still "
                    "cover extraction and matching; run this locally to test the "
                    "download path itself.",
                )
            return EndpointResult(
                "youtube_real_download",
                query,
                "MusicScraper",
                False,
                None,
                f"App download path failed: {type(exc).__name__}: {str(exc)[:140]}",
            )
        if not landed or not Path(landed).exists():
            return EndpointResult(
                "youtube_real_download",
                query,
                "MusicScraper",
                False,
                None,
                "App download path reported success but produced no audio file",
            )
        size = Path(landed).stat().st_size
        ok = size > 100_000  # a truncated or silent stub is not a download
        return EndpointResult(
            "youtube_real_download",
            query,
            "MusicScraper",
            ok,
            None,
            f"{Path(landed).name}, {size} bytes"
            if ok
            else f"Suspiciously small file: {size} bytes",
        )


def check_retry_clients_are_live() -> EndpointResult:
    """Every retry client must still be one yt-dlp ships.

    Cheap and offline: names YouTube retires get dropped silently at
    runtime, which quietly shrinks the recovery path until it is empty.
    """
    from Spotify_Downloader import _RETRY_CLIENTS

    live = _retry_player_clients()
    retired = [name for name in _RETRY_CLIENTS if name not in live]
    return EndpointResult(
        "youtube_retry_clients",
        ",".join(_RETRY_CLIENTS),
        "introspection",
        not retired,
        None,
        f"all {len(live)} retry clients still shipped by yt-dlp"
        if not retired
        else f"RETIRED by yt-dlp, recovery path shrinking: {retired} (live: {list(live)})",
    )


def check_unavailable_detection(api: SpotifyEmbedAPI, good_track_id: str) -> EndpointResult:
    """Spotify's error page must stay distinguishable from real content.

    Drives the region/private/removed message. If Spotify reshapes either
    page this stops discriminating, and users get a parser dump again.
    """
    url = "https://open.spotify.com/embed/track/0000000000000000000000"
    try:
        api.get_track("0000000000000000000000")
        return EndpointResult(
            "spotify_unavailable_detection",
            url,
            "GET",
            False,
            None,
            "Unavailable content did not raise ContentUnavailableError",
        )
    except ContentUnavailableError:
        pass
    except Exception as exc:
        return EndpointResult(
            "spotify_unavailable_detection",
            url,
            "GET",
            False,
            None,
            f"Unavailable content raised {type(exc).__name__} instead of ContentUnavailableError",
        )
    try:
        api.get_track(good_track_id)
    except Exception as exc:
        return EndpointResult(
            "spotify_unavailable_detection",
            url,
            "GET",
            False,
            None,
            f"FALSE POSITIVE: healthy track now raises {type(exc).__name__}: {exc}",
        )
    return EndpointResult(
        "spotify_unavailable_detection",
        url,
        "GET",
        True,
        None,
        "Error page raises ContentUnavailableError; healthy content unaffected",
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

    # Staleness guards: these caught nothing when they didn't exist, which
    # is the point - each covers a path that degraded silently in the past.
    results.append(check_retry_clients_are_live())
    results.append(
        check_real_download(
            MusicScraper(),
            f"ytsearch1:{query} audio",  # same shape _download_one_track builds
            "Never Gonna Give You Up",
        )
    )
    results.append(check_unavailable_detection(embed_api, album_probe_track_id))

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
    critical_checks = [
        "spotify_embed_api",
        "youtube_search",
        "youtube_real_download",
        "youtube_retry_clients",
        "spotify_unavailable_detection",
    ]
    failed_critical = [r for r in results if r.name in critical_checks and not r.ok]
    return 1 if failed_critical else 0


if __name__ == "__main__":  # pragma: no cover - manual diagnostic
    raise SystemExit(main())
