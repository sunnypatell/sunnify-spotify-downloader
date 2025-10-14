# External API Status (PyQt Desktop Downloader)

The legacy desktop client (`Spotify_Downloader.py`) depends on a handful of
unofficial endpoints for Spotify metadata, download links, and YouTube
transcoding. The following table captures their status as of the latest manual
check.

| Endpoint | Purpose in app | Test method | Result |
| --- | --- | --- | --- |
| `https://api.spotifydown.com/trackList/playlist/<playlist_id>` | Retrieves full playlist track listing | `scripts/check_api_status.py` → `spotifydown_track_list` | **Fail** – HTTP 503 with body `"DNS resolution failure"` |
| `https://api.spotifydown.com/metadata/playlist/<playlist_id>` | Fetches playlist title/artist metadata | `scripts/check_api_status.py` → `spotifydown_playlist_metadata` | **Fail** – HTTP 503 with body `"DNS resolution failure"` |
| `https://api.spotifydown.com/getId/<track_id>` | Converts Spotify track ID to YouTube ID | `scripts/check_api_status.py` → `spotifydown_get_id` | **Fail** – HTTP 503 with body `"DNS resolution failure"` |
| `https://api.spotifydown.com/download/<track_id>` | Retrieves pre-generated MP3 link | `scripts/check_api_status.py` → `spotifydown_download` | **Fail** – HTTP 503 with body `"DNS resolution failure"` |
| `https://corsproxy.io/?https://www.y2mate.com/mates/analyzeV2/ajax` | Fallback to y2mate analyze endpoint via CORS proxy | `scripts/check_api_status.py` → `corsproxy_y2mate_analyze` | **Fail** – HTTP 403, response indicates the target domain is blocked |
| `https://corsproxy.io/?https://www.y2mate.com/mates/convertV2/index` | Fallback to y2mate convert endpoint via CORS proxy | `scripts/check_api_status.py` → `corsproxy_y2mate_convert` | **Fail** – HTTP 403, response indicates the target domain is blocked |

## How to re-run the check

```bash
python3 scripts/check_api_status.py
```

The script prints a JSON array with the HTTP status and a short response
snippet for every endpoint probed, so you can quickly spot regressions.

If any endpoint starts responding again, replace the failing service inside
`Spotify_Downloader.py` with a stable alternative before shipping updates to
users.
