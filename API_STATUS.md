# External API Status (PyQt Desktop Downloader)

The desktop client now prefers Spotify's own public web endpoints to resolve
playlist metadata and track lists without requiring developer credentials. When
those calls are blocked it falls back to the usual spotifydown mirrors for
track discovery plus direct MP3 links. YouTube remains the last-resort audio
source via `yt-dlp`.

## Playlist metadata & track discovery

| Check | What it does | How to verify |
| --- | --- | --- |
| `playlist_client_lookup` | Exercises the combined resolver that first tries Spotify's web API and then spotifydown. The notes include the detected playlist title and a few sample tracks. | Run `python3 scripts/check_api_status.py`. |
| `spotify_web_playlist_lookup` | Directly queries `https://api.spotify.com/v1/playlists/{id}` using the anonymous web-player token. | Same as above; if this fails in your region, expect the combined lookup to fall back to spotifydown. |
| `spotifydown_playlist_lookup` | Calls `/trackList/playlist/{id}` on the first configured spotifydown base URL. | Same as above. Override `SPOTIFYDOWN_BASE_URLS` if the default hosts are blocked on your network. |

## Spotifydown-style APIs

| Check | What it does | How to verify |
| --- | --- | --- |
| `spotifydown_track_download` | Hits `/download/{trackId}` for the first track returned by the playlist call to confirm a direct MP3 URL is provided. | Run `python3 scripts/check_api_status.py`. |

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

macOS or Linux:

```bash
python3 scripts/check_api_status.py
```

Windows PowerShell:

```powershell
python .\scripts\check_api_status.py
```

The script prints a JSON array summarising each dependency. All entries should report `"ok": true` before demoing the downloader.

Example snippet:

```json
[
	{
		"name": "playlist_client_lookup",
		"ok": true,
		"notes": "Playlist 'Today's Top Hits'. Sample tracks: ..."
	},
	{
		"name": "youtube_search",
		"ok": true,
		"notes": "Resolved 'Rick Astley Never Gonna Give You Up' to ..."
	}
]
```
