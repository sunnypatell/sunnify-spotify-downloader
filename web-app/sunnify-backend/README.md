# Sunnify Backend

Lightweight Flask API that fetches Spotify playlist and track **metadata** (no audio). Powers the [web client](../sunnify-webclient); for actual MP3 downloads, use the desktop app or its bundled CLI.

Optimized for free-tier hosting (512MB RAM, 0.1 CPU): a single reusable client, aggressive GC, metadata-only responses.

## Endpoints

| Method | Path | Purpose |
| :--- | :--- | :--- |
| `POST` | `/api/scrape-playlist` | Resolve a playlist/album/track URL to its track metadata |
| `GET` | `/api/health` | Liveness probe (`{"status":"ok"}`) |
| `GET` | `/` | Service info + endpoint list |

`POST /api/scrape-playlist` body: `{"playlistUrl": "https://open.spotify.com/..."}` (playlist, album, or track URL / `spotify:` URI). The response's `data.truncated` is `true` when a playlist was longer than the track cap.

Errors always use the same envelope, `{"event": "error", "data": {"message": "..."}}`, with the HTTP status saying what kind: `400` bad input, `404`/`405` wrong route or method, `413` body too large, `429` rate limited (with `Retry-After`), `500` upstream or server fault.

## Limits and hardening

The endpoint is public and unauthenticated, and each scrape fans out into one Spotify request per track, so it is metered:

| Setting | Default | What it does |
| :--- | :--- | :--- |
| `SUNNIFY_CORS_ORIGINS` | `https://sunnify-spotify-downloader.vercel.app,http://localhost:3000` | Comma-separated browser origins allowed to call the API |
| `SUNNIFY_RATE_LIMIT` | `20` | Scrapes per client IP per minute (sliding window, per process) |
| `SUNNIFY_MAX_TRACKS` | `1000` | Tracks returned per playlist; longer ones come back with `truncated: true` |
| `HOST` / `PORT` | `127.0.0.1` / `5000` | The dev server's bind address (`gunicorn` takes `--bind` instead) |

Also always on: request bodies over 16 KB are refused with `413`, the client IP for rate limiting is read from exactly one proxy hop of `X-Forwarded-For` (Render's), and every response carries `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, a deny-all `Content-Security-Policy` and `Cache-Control: no-store`.

## Run locally

```bash
pip install -r requirements.txt
python app.py            # dev server on 127.0.0.1:5000 (HOST/PORT overridable)
gunicorn app:app         # production (matches Procfile / Render)
```

## Deploy

Deployed on Render via `Procfile` (`web: gunicorn app:app`). The repo's [health-check workflow](../../.github/workflows/render-health.yml) pings `/api/health` every 6h to monitor uptime and reduce cold starts.

Shares the Spotify embed-API client (`spotifydown_api.py`) with the desktop app, so no credentials are required.
