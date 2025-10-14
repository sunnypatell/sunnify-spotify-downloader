# External API Status (PyQt Desktop Downloader)

The desktop client once again relies on third-party spotifydown endpoints to
obtain playlist metadata and direct download links without requiring Spotify
credentials. YouTube remains the fallback via `yt-dlp` when the direct link is
missing or stale.

## Spotifydown-style APIs

| Check | What it does | How to verify |
| --- | --- | --- |
| `spotifydown_playlist_lookup` | Calls `/trackList/playlist/{id}` on the first
configured base URL and reports the playlist title plus a few sample tracks. |
Run `python3 scripts/check_api_status.py`. Override
`SPOTIFYDOWN_BASE_URLS` if the default hosts are blocked on your network. |
| `spotifydown_track_download` | Hits `/download/{trackId}` for the first track
returned by the playlist call to confirm a direct MP3 URL is provided. | Same as
above. |

If both checks fail, rotate the domain list via
`SPOTIFYDOWN_BASE_URLS="https://your-mirror/api"` and rerun the script.

## YouTube via `yt-dlp`

| Check | What it does | How to verify |
| --- | --- | --- |
| `youtube_search` | Uses `yt-dlp`'s `ytsearch1:` extractor to locate the first
matching video for a test query without downloading media. | Run
`python3 scripts/check_api_status.py`. |

When the search fails, check your network connection or update `yt-dlp` to the
latest release.

## Rerunning the diagnostics

```bash
python3 scripts/check_api_status.py
```

On Windows PowerShell replace `python3` with `python` if needed. The script
prints a JSON array summarising each dependency. All entries should report
`"ok": true` before demoing the downloader.
