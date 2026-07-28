# Sunnify CLI

Every Sunnify binary is also a headless CLI: run it with a command and it never
opens a window; run it with no arguments and you get the desktop app. Both
faces share one engine: the same YouTube matcher, file naming, tag writer,
resume manifest, and `config.json`. A download scripted at 2 AM behaves
exactly like one clicked in the GUI.

```
sunnify download "https://open.spotify.com/playlist/..."
```

## Install

The CLI ships inside the app you already have. Getting `sunnify` on PATH:

| Platform | Command |
| :--- | :--- |
| **macOS (Homebrew)** | `brew tap sunnypatell/sunnify https://github.com/sunnypatell/sunnify-spotify-downloader && brew install --cask sunnify` |
| **macOS / Linux (script)** | `curl -fsSL https://raw.githubusercontent.com/sunnypatell/sunnify-spotify-downloader/main/scripts/install.sh \| sh` |
| **Windows (PowerShell)** | `iwr -useb https://raw.githubusercontent.com/sunnypatell/sunnify-spotify-downloader/main/scripts/install.ps1 \| iex` |
| **Any OS (pipx/uv, from source)** | `pipx install git+https://github.com/sunnypatell/sunnify-spotify-downloader` |

Install notes, by design:

- **No prompts, no elevation.** Everything is user-scope (`~/Applications` +
  `~/.local/bin` on macOS/Linux, `%LOCALAPPDATA%\Sunnify` + user PATH on
  Windows). No sudo, no UAC dialog, nothing that blocks an automated shell.
- **Verified downloads.** The scripts fetch official release assets and check
  their SHA256 against the release's `checksums.txt` before installing;
  these are the same assets covered by the project's
  [SLSA build provenance](../SECURITY.md#release-integrity).
- **Re-running updates in place.** Both scripts are idempotent.

## Updating

The GUI shows a banner when a newer release exists. Headless runs never
phone home, so the CLI reports it only when asked: `sunnify doctor` includes
a `version` check with the release page URL when you are behind. To update,
run `brew upgrade --cask sunnify` if Homebrew owns the install, or re-run
the install one-liner above; both are prompt-free, so agents can run them
too.

## Commands

| Command | What it does |
| :--- | :--- |
| `sunnify download <url>` | Download a playlist, album, or track |
| `sunnify info <url>` | Fetch metadata only (no downloads, no FFmpeg needed) |
| `sunnify status [folder]` | Audio files present, manifest state, active download pid |
| `sunnify config [--set k=v]` | Show or persist settings (the same `config.json` the GUI uses) |
| `sunnify doctor` | Self-check: FFmpeg, config, Spotify reachability, yt-dlp, and whether a newer release exists |
| `sunnify --version` / `--help` | You know these (`sunnify help [command]` works too) |

A mistyped command errors with a suggestion (`did you mean 'download'?`)
instead of launching the app.

### download

```
sunnify download <url> [--out DIR] [--format mp3|m4a|opus|flac|wav]
                       [--quality 128|192|256|320] [--sample-rate auto|44100|48000]
                       [--track-numbers | --no-track-numbers]
                       [--artist-first | --no-artist-first]
                       [--loose-match | --no-loose-match]
                       [--json] [--quiet]
```

- Defaults come from your saved settings; flags override per run. `--help`
  always shows the current effective defaults.
- Tracks already on disk are skipped, so re-running a playlist **resumes** it.
- A per-folder pid lock stops two runs from racing the same destination.
- First `Ctrl+C` finishes in-flight tracks and exits cleanly; a second one
  force-quits.

### Exit codes

| Code | Meaning |
| :--- | :--- |
| `0` | Everything requested is on disk |
| `1` | Run completed but some tracks failed or the run was stopped |
| `2` | Usage error (bad flag/argument) |
| `3` | Environment or fatal error (bad URL, no FFmpeg, locked folder, ...) |

## Machine-readable output (`--json`)

`download --json` emits NDJSON: one event per line, always ending with
`run_summary`:

```json
{"event": "run_started", "url": "...", "type": "playlist", "folder": "...", "format": "mp3", "quality": "320", "sample_rate": "auto", "artist_first": false, "track_numbers": true, "loose_match": false}
{"event": "track_done", "title": "...", "artists": "...", "file": "/path/file.mp3", "bytes": 4823041}
{"event": "track_skipped", "title": "...", "file": "/path/file.mp3"}
{"event": "warning", "message": "..."}
{"event": "run_summary", "landed": 12, "skipped": 3, "failed": 1, "failed_titles": ["..."], "stopped": false, "elapsed_s": 94.2, "folder": "...", "exit_code": 1}
```

Errors are typed envelopes; branch on `code`, not on message text:

```json
{"event": "error", "code": "ffmpeg_missing", "message": "ffmpeg not found", "hint": "..."}
```

Current codes: `invalid_url`, `out_dir_unusable`, `ffmpeg_missing`,
`folder_locked`, `metadata_fetch_failed`, `run_failed`.

`info`, `status`, `config`, and `doctor` print a single JSON document with
`--json`.

## For AI agents

This CLI is designed to be driven autonomously (per the
[command line interface guidelines](https://clig.dev/)):

- Nothing is interactive: no command ever waits for input or elevates
  privileges, and the installers follow the same rule.
- `--json` output is a stable contract; `run_summary` is the stream
  terminator.
- Long playlist? Run it in the background; `sunnify status <folder>` reports
  progress from another shell (files land incrementally, the lock pid tells
  you it's still running).
- Something failing? `sunnify doctor --json` says which dependency or
  upstream is broken, with hints.
- Windows note: when launched from an interactive console the windowed exe
  returns the prompt immediately; pipe the output (`sunnify doctor | Out-Default`)
  to make the shell wait. Redirected and piped output, which is how agents
  run tools, behaves normally without any of that.

## Where things live

| Thing | Location |
| :--- | :--- |
| Settings | One shared `config.json`: `sunnify config --set` and the GUI's settings panel read and write the same file, so a choice made in either face applies to both. Flags override it per run. |
| Logs | Same rotating session log as the app (`sunnify doctor` shows the dir; "Open logs folder" in the GUI) |
| Resume manifest | `.sunnify-manifest.jsonl` inside each playlist folder |
| Run lock | `.sunnify-cli.lock` inside the destination folder |
