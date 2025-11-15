<div align="center">

<h1>Sunnify (Spotify Downloader)</h1>

<a href="https://github.com/sunnypatell/sunnify-spotify-downloader/stargazers"><img alt="Stars" src="https://img.shields.io/github/stars/sunnypatell/sunnify-spotify-downloader?style=social"></a>
<a href="https://github.com/sunnypatell/sunnify-spotify-downloader/issues"><img alt="Issues" src="https://img.shields.io/github/issues/sunnypatell/sunnify-spotify-downloader"></a>
<a href="https://github.com/sunnypatell/sunnify-spotify-downloader/pulls"><img alt="PRs" src="https://img.shields.io/github/issues-pr/sunnypatell/sunnify-spotify-downloader"></a>
<a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/license-Custom-important"></a>

<br/>

<img src="./app.png" alt="Sunnify" height="96" />

<p><em>🎧 Download entire Spotify playlists to local MP3s with embedded artwork and tags. Desktop app, Python core, and a full web stack in one repo.</em></p>

</div>

<p align="center">
    <a href="#table-of-contents">Jump to Table of Contents</a>
</p>

<hr/>

## Table of Contents

1. Overview
2. Architecture
3. Features
4. Requirements
5. Quick Start (3 Paths)
6. Desktop App Setup (Windows and cross-platform)
7. Web App Setup (Backend and Frontend)
8. Configuration
9. Usage Guide
10. Diagnostics
11. Troubleshooting
12. Notes and Roadmap
13. Security and Legal
14. Contributing and Community
15. Author

<hr/>

## Overview

Sunnify is built to be resilient, fast, and simple:

- Falls back from Spotify's public web API to multiple spotifydown-style mirrors.
- Resolves direct MP3 links when available; otherwise uses `yt-dlp` with FFmpeg.
- Writes clean ID3 tags and embeds cover art for your library.
- Ships as a PyQt desktop app, a Flask API, and a modern Next.js web client.

Screenshots from the desktop app in action:

<img src="/readmeAssets/demonstration%201.jpg" alt="Download" width="48%"/> <img src="/readmeAssets/demonstration%202.jpg" alt="Preview" width="48%"/>

<hr/>

## Architecture

```
root
├─ Spotify_Downloader.py          (PyQt5 desktop app)
├─ spotifydown_api.py             (Provider abstraction: Spotify Web + spotifydown)
├─ Template.py / Template.ui      (Generated UI for the desktop app)
├─ scripts/
│  └─ check_api_status.py         (Diagnostics for mirrors, Spotify web, yt-dlp)
├─ dist/
│  └─ Sunnify (Spotify Downloader).exe   (Prebuilt Windows executable)
├─ web-app/
│  ├─ sunnify-backend/            (Flask API: SSE + JSON responses)
│  │  ├─ app.py                   (/api/scrape-playlist, /api/download)
│  │  ├─ requirements.txt         (Backend dependencies)
│  │  └─ Procfile                 (gunicorn entry)
│  └─ sunnify-webclient/          (Next.js 14 + Tailwind + shadcn/ui)
│     ├─ app/page.tsx             (Renders <SunnifyApp />)
│     └─ components/sunnify-app.tsx  (Main UI + API integration)
├─ req.txt                        (Desktop app Python deps)
├─ Sunnify (Spotify Downloader).spec  (PyInstaller build spec)
└─ README.md
```

<hr/>

## Features

- 🎼 Full playlist downloader (one link to a tagged MP3 library)
- 🖼️ Artwork and tagging (title, artists, album, release date, cover art)
- 🚦 Smart providers (Spotify Web API with fallback to spotifydown mirrors)
- 🎯 Resilient audio pipeline (direct links or `yt-dlp` fallback)
- 🪟 Clean desktop UI (progress, preview panel, per-track status)
- 🌐 Web experience (Flask backend and Next.js client)

<hr/>

## Requirements

- Python 3.8 or newer (3.6+ supported, 3.8+ recommended)
- FFmpeg on PATH (required by `yt-dlp` for MP3 conversion)
- Node.js 18 or newer (for the web client)
- Internet access to `open.spotify.com` and mirror providers

<details>
<summary>Install FFmpeg (Windows, macOS, Linux)</summary>

- Windows: use winget or choco, then restart terminal so PATH updates

```powershell
winget install Gyan.FFmpeg
# or
choco install ffmpeg
```

- macOS: use Homebrew

```bash
brew install ffmpeg
```

- Ubuntu/Debian

```bash
sudo apt update
sudo apt install -y ffmpeg
```

Verify with `ffmpeg -version`.

</details>

<hr/>

## Quick Start (3 Paths)

- Windows users: download the prebuilt app `dist/Sunnify (Spotify Downloader).exe` and run it.
- Python users: `pip install -r req.txt` then `python Spotify_Downloader.py`.
- Web stack: run the Flask backend and Next.js client under `web-app/`.

<hr/>

## Desktop App Setup (Windows and cross-platform)

Windows PowerShell commands:

```powershell
# Clone
git clone https://github.com/sunnypatell/sunnify-spotify-downloader.git
cd sunnify-spotify-downloader

# Create and activate a venv (recommended)
py -3 -m venv .venv; .\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r req.txt

# Ensure FFmpeg is on PATH
ffmpeg -version

# Optional: override mirrors
$Env:SPOTIFYDOWN_BASE_URLS = "https://api.spotifydown.com,https://spotimate.io/api"

# Launch the PyQt app
python .\Spotify_Downloader.py
```

macOS/Linux equivalent:

```bash
git clone https://github.com/sunnypatell/sunnify-spotify-downloader.git
cd sunnify-spotify-downloader
python3 -m venv .venv && source .venv/bin/activate
pip install -r req.txt
ffmpeg -version
export SPOTIFYDOWN_BASE_URLS="https://api.spotifydown.com,https://spotimate.io/api"
python Spotify_Downloader.py
```

Build a Windows EXE with PyInstaller:

```powershell
.\.venv\Scripts\Activate.ps1
pyinstaller "Sunnify (Spotify Downloader).spec"
```

Output files are placed in `dist/`.

<hr/>

## Web App Setup (Backend and Frontend)

### Backend (Flask)

```powershell
cd web-app\sunnify-backend
py -3 -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python .\app.py
# Serves on http://127.0.0.1:5000
```

Endpoints:

- `POST /api/scrape-playlist` processes a playlist and emits progress or completion events.
- `GET /api/download/<filename>?path=<dir>` serves a file from a directory.

The local server can stream Server-Sent Events (SSE). Each event looks like:
`{"event":"progress"|"complete"|"error","data":{...}}`.

Production style run with gunicorn:

```powershell
pip install gunicorn
gunicorn app:app --bind 0.0.0.0:5000
```

### Frontend (Next.js)

```powershell
cd ..\sunnify-webclient
npm install
npm run dev
# Opens http://localhost:3000
```

Configure API base in `.env.local` (recommended):

```dotenv
NEXT_PUBLIC_API_BASE=http://127.0.0.1:5000
```

Then update `components/sunnify-app.tsx` to use `process.env.NEXT_PUBLIC_API_BASE + '/api/scrape-playlist'`.

Local production simulation:

```powershell
npm run build
npm start
```

Note: the current client points at a hosted AWS Lambda URL by default. Switch it to your local Flask server for development and, if desired, add an SSE consumer for realtime progress.

<hr/>

## Configuration

- `SPOTIFYDOWN_BASE_URLS` a comma-separated mirror list to override defaults
    - PowerShell example: ``$Env:SPOTIFYDOWN_BASE_URLS = "https://api.spotifydown.com,https://spotimate.io/api"``
- `NEXT_PUBLIC_API_BASE` base URL for the webclient backend (set via `.env.local`)

<details>
<summary>Advanced configuration tips</summary>

- Corporate networks can block `open.spotify.com` and mirrors. Allowlist domains or provide custom mirrors via `SPOTIFYDOWN_BASE_URLS`.
- Increase request timeouts only if your network is unusually slow. See `spotifydown_api.py` for defaults.
- Ensure Windows download paths have write permissions.

</details>

<hr/>

## Usage Guide

Desktop app (GUI):

1. Launch Sunnify.
2. Paste a Spotify playlist URL `https://open.spotify.com/playlist/<ID>`.
3. Press Enter in the URL box to start.
4. Optional: enable Show Preview to see the cover and meta.
5. Optional: enable Add Meta Tags to embed ID3 and artwork.
6. Output appears under `music/<Playlist Name - Owner>/` next to the app.

Web client:

1. Start Flask backend and Next.js client.
2. Open `http://localhost:3000`.
3. Enter playlist URL and a writable download path.
4. Click Process Playlist and watch progress.

<hr/>

## Deep Dive: How It Works

### Provider Strategy (spotifydown_api.py)

- `SpotifyPublicAPI` fetches an anonymous web token from `open.spotify.com`, then calls `api.spotify.com/v1` for playlist and tracks.
- `SpotifyDownAPI` rotates across multiple mirror base URLs to resolve playlist metadata, tracks, MP3 links, and YouTube IDs.
- `PlaylistClient` tries Spotify Web first, then spotifydown; provides direct link and YouTube ID helpers.

Environment override: set `SPOTIFYDOWN_BASE_URLS` to replace default mirrors.

### Download Pipeline (Desktop App)

For each track:

1. Ask for a direct MP3 link (`/download/<track_id>`) via spotifydown.
2. If missing, request YouTube ID, then use the watch URL.
3. If still missing, fallback search: `ytsearch1:<title> <artists> audio`.
4. Convert to MP3 (`yt-dlp` plus FFmpeg) and write ID3 tags (Mutagen).
5. Embed cover art (from track or playlist metadata).

### Web Backend (web-app/sunnify-backend/app.py)

- `POST /api/scrape-playlist` can stream JSON events (SSE) while processing.
- Completion event includes `playlistName` and `tracks` with download links.

<hr/>

## Diagnostics

Validate mirrors, Spotify Web, and `yt-dlp` from your network:

```powershell
python .\scripts\check_api_status.py
```

Example output summarizes which providers resolved metadata, sample tracks, and whether YouTube search succeeded.

<hr/>

## Troubleshooting

- FFmpeg not found: install FFmpeg and restart terminal so PATH updates.
- `yt-dlp` errors: `pip install -U yt-dlp` and ensure YouTube is reachable.
- Playlist URL rejected: format must be `https://open.spotify.com/playlist/<ID>`.
- Hosted backend cold starts: free tiers can sleep; first call might take seconds.
- Mirrors down: set `SPOTIFYDOWN_BASE_URLS` to a working mirror list.
- Windows permissions: choose a download path you can write to.

<hr/>

## Notes and Roadmap

Important note (hosted backends): on free compute plans, the backend might sleep and take a moment to wake on the first request.

Coming soon:

- Apple Music and iTunes import
- Android MTP copy support
- Webclient SSE progress UI

<hr/>

## Security and Legal

⚠️ Educational use only. Ensure compliance with copyright laws in your jurisdiction. Do not use this project to infringe on rights holders.

See [SECURITY.md](SECURITY.md) for reporting vulnerabilities and [LICENSE](LICENSE) for license terms.

<hr/>

## Contributing and Community

Contributions, ideas, and bug reports are welcome.

- Read the [CODE_OF_CONDUCT](CODE_OF_CONDUCT.md) and [CONTRIBUTING](CONTRIBUTING.md)
- Open issues with clear repro steps and logs where possible
- Prefer small, focused PRs

<hr/>

## Author

Created and maintained by Sunny Jayendra Patel. Reach me at `sunnypatel124555@gmail.com` or connect on LinkedIn.

</div>
