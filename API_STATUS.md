# External API Status

Sunnify v2.0.1 uses Spotify's embed page endpoints to fetch playlist and track
metadata without requiring developer credentials. YouTube (via `yt-dlp`) is used
for audio downloads.

## Current API Architecture

### Primary: Spotify Embed Page API

| Endpoint | Purpose | Notes |
| --- | --- | --- |
| `/embed/playlist/{id}` | Playlist metadata + up to 100 tracks | Extracts `__NEXT_DATA__` JSON blob |
| `/embed/track/{id}` | Single track metadata | Used for individual track downloads |
| `/oembed?url=...` | Quick playlist validation | Fast existence check |

### Fallback: spclient API (for large playlists)

For playlists with >100 tracks, Sunnify uses an anonymous access token extracted
from embed pages to query `spclient.wg.spotify.com/playlist/v2/playlist/{id}`
for the complete track URI list, then fetches individual track metadata via
embed pages.

### Audio Downloads: YouTube via yt-dlp

All audio is sourced from YouTube using `yt-dlp`'s `ytsearch1:` extractor.
The search query format is: `ytsearch1:{title} {artists} audio`

## Deprecated Endpoints (No Longer Used)

The following endpoints are **no longer functional** and have been removed:

- `api.spotifydown.com` - All mirrors are dead (403/blocked)
- `spotimate.io/api` - No longer responding
- `open.spotify.com/get_access_token` - Returns 403 for anonymous requests
- `api.spotify.com/v1/playlists/{id}` - Requires OAuth (anonymous blocked)

The `SPOTIFYDOWN_BASE_URLS` environment variable is no longer used.

## Running Diagnostics

Verify all endpoints from your network:

```bash
# macOS/Linux
python3 scripts/check_api_status.py

# Windows PowerShell
python .\scripts\check_api_status.py
```

Example output:

```
============================================================
API STATUS SUMMARY
============================================================

spotify_embed_api: OK
  URL: https://open.spotify.com/embed/playlist/37i9dQZF1DXcBWIGoYBM5M
  Notes: Playlist 'Today's Top Hits' by Spotify. Sample tracks: ...

playlist_client: OK
  URL: PlaylistClient for 37i9dQZF1DXcBWIGoYBM5M
  Notes: Playlist 'Today's Top Hits' by Spotify. Sample tracks: ...

oembed_validation: OK
  URL: https://open.spotify.com/oembed?url=...
  Notes: Playlist validation successful

large_playlist_fallback: OK
  URL: spclient + individual embeds for 37i9dQZF1DX5Ejj0EkURtP
  Notes: Retrieved all 150 tracks (expected 150)

youtube_search: OK
  URL: ytsearch1:Rick Astley Never Gonna Give You Up
  Notes: Resolved 'Rick Astley Never Gonna Give You Up' to ...

youtube_track_search: OK
  URL: ytsearch1:{track} audio
  Notes: Track resolved to YouTube video
============================================================
```

All entries should report `OK` before using the downloader.

## Troubleshooting

- **Embed page fails**: Check if `open.spotify.com` is accessible from your network
- **Large playlist incomplete**: The spclient fallback requires a valid access token from embed pages
- **YouTube search fails**: Run `pip install -U yt-dlp` and ensure YouTube is reachable
- **Playlist URL rejected**: Format must be `https://open.spotify.com/playlist/{id}` or `https://open.spotify.com/track/{id}`
