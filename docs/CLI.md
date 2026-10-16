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
| **macOS (Homebrew)** | `brew tap sunnypatell/sunnify https://github.com/sunnypatell/sunnify-spotify-downloader && brew install --cask sunnypatell/sunnify/sunnify` |
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
run `brew upgrade --cask sunnypatell/sunnify/sunnify` if Homebrew owns the
install (the full name works even where Homebrew has not been told to trust
the tap yet), or re-run the install one-liner above; both are prompt-free,
so agents can run them too.

## Commands

| Command | What it does |
| :--- | :--- |
| `sunnify download <url>` | Download a playlist, album, or track |
| `sunnify info <url>` | Fetch metadata only (no downloads, no FFmpeg needed) |
| `sunnify status [folder]` | Audio files present, manifest state, active download pid |
| `sunnify config [--set k=v]` | Show or persist settings (the same `config.json` the GUI uses) |
| `sunnify doctor` | Self-check: FFmpeg, config, Spotify reachability, yt-dlp, YouTube cookies, and whether a newer release exists |
| `sunnify --version` / `--help` | You know these (`sunnify help [command]` works too) |

A mistyped command errors with a suggestion (`did you mean 'download'?`)
instead of launching the app.

### download

```
sunnify download <url> [--out DIR] [--format mp3|m4a|opus|flac|wav]
                       [--quality 128|192|256|320] [--sample-rate auto|44100|48000]
                       [--track-numbers | --no-track-numbers]
                       [--artist-first | --no-artist-first]
                       [--title-only | --no-title-only]
                       [--loose-match | --no-loose-match]
                       [--cookies FILE]
                       [--json] [--quiet]
```

- Defaults come from your saved settings; flags override per run. `--help`
  always shows the current effective defaults.
- Tracks already on disk are skipped, so re-running a playlist **resumes** it.
- A per-folder pid lock stops two runs from racing the same destination.
- First `Ctrl+C` finishes in-flight tracks and exits cleanly; a second one
  force-quits.
- `--cookies FILE` is only for networks YouTube gates; see
  [YouTube cookies](#youtube-cookies).

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
{"event": "run_started", "url": "...", "type": "playlist", "folder": "...", "format": "mp3", "quality": "320", "sample_rate": "auto", "artist_first": false, "title_only": false, "track_numbers": true, "loose_match": false, "cookies": false}
{"event": "track_done", "title": "...", "artists": "...", "file": "/path/file.mp3", "bytes": 4823041}
{"event": "track_skipped", "title": "...", "file": "/path/file.mp3"}
{"event": "warning", "message": "..."}
{"event": "run_summary", "landed": 12, "skipped": 3, "failed": 1, "failed_titles": ["..."], "stopped": false, "elapsed_s": 94.2, "folder": "...", "exit_code": 1}
```

Errors are typed envelopes; branch on `code`, not on message text:

```json
{"event": "error", "code": "ffmpeg_missing", "message": "ffmpeg not found", "hint": "..."}
```

Current codes: `invalid_url`, `conflicting_flags`, `out_dir_unusable`,
`ffmpeg_missing`, `cookies_unusable`, `deno_missing`, `folder_locked`,
`metadata_fetch_failed`, `run_failed`.
(`conflicting_flags` fires on explicit `--title-only --artist-first`; a
title-only filename has no order, so pass one or the other.)

`info`, `status`, `config`, and `doctor` print a single JSON document with
`--json`.

## YouTube cookies

YouTube sometimes asks a whole network to prove it isn't a bot, and then
refuses every download from it. Sunnify says so once, in plain words, instead
of failing each track separately. Switching networks usually clears it. Where
that isn't an option, you can give Sunnify the cookies of your own logged-in
YouTube session. Without this setting, nothing about how Sunnify talks to
YouTube changes.

You need two things:

1. **A Netscape-format `cookies.txt`** with your youtube.com cookies. The
   [yt-dlp wiki](https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies)
   shows how to export one. Use a dedicated browser profile or a private
   window, ideally with a secondary account. YouTube can flag an account used
   this way, and the file should be treated like a password.
2. **[Deno](https://docs.deno.com/runtime/getting_started/installation/)**, a
   JavaScript runtime. A logged-in session only gets YouTube player variants
   that require solving a JavaScript challenge, and yt-dlp runs the solver
   (bundled with Sunnify) in Deno's sandbox. Sunnify finds Deno on your `PATH`
   or in its default install location.

Turn it on for one run with `--cookies ~/youtube-cookies.txt`, or for every run
(desktop app included) with `sunnify config --set cookies_file=~/youtube-cookies.txt`.
`--cookies ''` skips a saved file for one run, and
`sunnify config --set cookies_file=` turns it off.

Sunnify only ever reads the file: each request gets a private temporary copy
of its valid cookies that is deleted afterwards, so your file is never
modified, and its contents never reach the logs or the terminal. A missing or
malformed file stops the run with `cookies_unusable`, and a missing Deno with
`deno_missing`; `sunnify doctor` checks both. If YouTube still refuses the
network with cookies loaded, they have usually expired; export them again.

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

## Where things live

| Thing | Location |
| :--- | :--- |
| Settings | One shared `config.json`: `sunnify config --set` and the GUI's settings panel read and write the same file, so a choice made in either face applies to both. Flags override it per run. |
| Logs | Same rotating session log as the app (`sunnify doctor` shows the dir; "Open logs folder" in the GUI) |
| Resume manifest | `.sunnify-manifest.jsonl` inside each playlist folder |
| Run lock | `.sunnify-cli.lock` inside the destination folder |
