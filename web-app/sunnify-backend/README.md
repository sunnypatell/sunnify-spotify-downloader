# Sunnify Backend

Lightweight Flask API that fetches Spotify playlist and track **metadata** (no audio). Powers the [web client](../sunnify-webclient); for actual MP3 downloads, use the desktop app.

Optimized for free-tier hosting (512MB RAM, 0.1 CPU): a single reusable client, aggressive GC, metadata-only responses.

## Endpoints

| Method | Path | Purpose |
| :--- | :--- | :--- |
| `POST` | `/api/scrape-playlist` | Resolve a playlist/album/track URL to its track metadata |
| `GET` | `/api/health` | Liveness probe (`{"status":"ok"}`) |
| `GET` | `/` | Service info + endpoint list |

`POST /api/scrape-playlist` body: `{"playlistUrl": "https://open.spotify.com/..."}` (playlist, album, or track URL / `spotify:` URI).

## Run locally

```bash
pip install -r requirements.txt
python app.py            # dev server on :5000 (PORT overridable)
gunicorn app:app         # production (matches Procfile / Render)
```

## Deploy

Deployed on Render via `Procfile` (`web: gunicorn app:app`). The repo's [health-check workflow](../../.github/workflows/render-health.yml) pings `/api/health` every 6h to monitor uptime and reduce cold starts.

Shares the Spotify embed-API client (`spotifydown_api.py`) with the desktop app, so no credentials are required.
