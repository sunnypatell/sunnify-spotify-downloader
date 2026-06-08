# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.0.8] - 2026-06-08

### Added
- **optional track-number prefix in filenames** (closes #44). settings now exposes a "Track number in filename:" checkbox. when on, downloaded files are prefixed with their zero-padded playlist position (`01. song - artist.mp3`, `02. ...`, ... `12. ...`) so the folder sorts in playlist order in any file manager. default off, so existing downloads are byte-for-byte unchanged; the position number is the same `TRCK` value that's already written to the ID3 tag, so this just surfaces existing data in the filename. primary contribution by @r-a-cristian-93 in #44; cleanups (3.9 compat via `from __future__ import annotations`, padded collision-guard, redundant bool validation dropped, default-off, tests) layered on top before merge.

### Fixed
- **mp3 cover art (and text tags) not showing in older players, car head-units, and stock android** (closes #46). mutagen defaults to ID3v2.4 with UTF-8 text encoding, but the v2.3 spec only defines two text encodings: `$00` ISO-8859-1 and `$01` Unicode (UTF-16 with BOM); the v2.4-only `$03` UTF-8 byte makes strict parsers (older iTunes/Apple Music, Windows Media Player, most car head-units, stock android) reject the frame, which manifests as "cover shows in preview but missing once downloaded" and (sometimes) missing title/artist/album. tags + the APIC cover frame are now written as v2.3 via `EasyID3.save(v2_version=3)` plus `id3.add(APIC(encoding=1, ...))` + `id3.update_to_v23()` + `id3.save(v2_version=3)`, which is the lowest-common-denominator format that's understood everywhere modern v2.4 is. APIC uses `encoding=1` (UTF-16+BOM), `type=3` ("Cover (front)"), and `desc='Cover'`. canonical `id3.add(APIC(...))` replaces the dict-style `id3["APIC"] = ...` assignment. refs: [ID3v2.3 spec section 3.3](https://id3.org/id3v2.3.0) (defines encodings $00 / $01); [ID3v2.4 spec](https://id3.org/id3v2.4.0-frames) (adds $02 UTF-16BE, $03 UTF-8); [mutagen `update_to_v23()`](https://mutagen.readthedocs.io/en/latest/api/id3.html) (UTF-8 -> UTF-16 downgrade).
- cover-art mime is now sniffed from the image's magic bytes for all three containers (mp3 APIC, m4a `covr`, FLAC `Picture`) instead of being hardcoded to `image/jpeg`. Spotify has served JPEG since at least 2015 (so today's behaviour doesn't change), but the previous code would silently produce a broken frame mis-tagged as JPEG if Spotify ever switches to PNG/WebP. refs: [JPEG SOI marker](https://www.w3.org/Graphics/JPEG/itu-t81.pdf) (`FF D8 FF`); [PNG signature](https://www.w3.org/TR/png/#5PNG-file-signature) (`89 50 4E 47 0D 0A 1A 0A`).

### Notes
- existing 2.0.7 downloads that have v2.4 + UTF-8 tags are not rewritten by 2.0.8; the change applies to new downloads. if you need to fix old files, re-downloading the affected track is the simplest path.
- m4a (`covr`) and FLAC (`Picture`) cover art is unaffected by the v2.3 work; those containers don't have the v2.3/v2.4 encoding distinction and were already correctly written.

## [2.0.7] - 2026-05-26

### Added
- **album downloads** (closes #38). album URLs and `spotify:album:` URIs now work alongside playlists and tracks. albums reuse the embed-parsing path through `/embed/album/{id}`, and because the album embed exposes the album name, every downloaded album track gets its `album` tag written (something playlist downloads can't provide, since playlist embeds don't carry it). verified end-to-end: a real album download writes `album=...` into the output file's tags.
- **resume support for large playlists** (closes #40). a per-playlist manifest (`.sunnify-manifest.jsonl`) inside each download folder records which tracks already landed. on a re-run, those tracks are skipped *before* their rate-limited `/embed/track/` metadata is fetched, so a playlist throttled by spotify's rate limit can be finished across several sessions instead of one long sit. entries whose files were deleted are pruned on load, so a removed track re-downloads. append-only json-lines keeps recording O(1) regardless of playlist size.

### Fixed
- wrong audio for some tracks: the file name was correct but it played a different recording (reported by email). the youtube search took the top hit, which is frequently the **music video** (extra intro/skit/outro) or an extended/remix cut, so the audio didn't match the spotify track. confirmed it was present in every prior version (old `ytsearch1` picked the same wrong result) and not caused by any mirror. download now flat-searches the top results and picks the candidate whose **duration matches the spotify track** (within ~7s), steering to the real audio instead of the music video; falls back to the top result only when no duration is known.
- tracks that scraped but never finished downloading (closes #42). the youtube search used `ytsearch1` (a single result), so a track whose top match was region-locked or removed failed outright; worse, `download_track_audio` returned the expected path even when no file was produced, so the app reported success for a download that never happened. the search now tries up to 5 results (skipping unavailable ones) with a simplified fallback query for hyper-specific titles (e.g. classical works with `(Op. 49, No. 4)`), and raises a clear "not found on YouTube" error when no audio lands. failures are now reported instead of silently hanging.
- accented and non-Latin characters were being stripped from filenames (reported on r/selfhosted). `sanitize_filename` used an ASCII-only allowlist, so titles like "MONTAGEM BAILÃO" lost the "Ã" and fully non-Latin titles (CJK, Cyrillic) collapsed to "Unknown". confirmed end-to-end that the loss was ours (Spotify returns the characters intact and yt-dlp/FFmpeg write them to disk fine). it now keeps every character except the ones the filesystem actually rejects: drops the Windows-reserved set `<>:"/\|?*` plus control characters, trims trailing dots/spaces, and escapes the Windows reserved device names (`CON`, `NUL`, `COM1`...). refs: Windows [Naming Files, Paths, and Namespaces](https://learn.microsoft.com/windows/win32/fileio/naming-a-file); macOS/Linux forbid only `/` and NUL ([POSIX portable filename set](https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/V1_chap03.html#tag_03_282)).
- windows exe version metadata: the `FixedFileInfo` `filevers` / `prodvers` tuples in `Sunnify.spec` were stuck at `2.0.3` (missed in the 2.0.4-2.0.6 bumps) while the string fields read the current version. both are now bumped together so the embedded Windows version is internally consistent.

## [2.0.6] - 2026-04-16

### Added
- **audio format + bitrate selection** in settings. choose between mp3, m4a, opus, flac, and wav, with 128/192/256/320 kbps for the lossy formats. the selection is persisted to disk (`~/Library/Application Support/Sunnify/config.json` on macos, `%APPDATA%\Sunnify` on windows, `$XDG_CONFIG_HOME/Sunnify` on linux) so it survives app restarts. end-to-end verified across all 10 format/quality combos via ffprobe (mp3 @ 128/192/256/320 kbps exact, m4a aac @ 129/327 kbps, opus, flac lossless, wav pcm_s16le @ 1536 kbps).
- **multi-format metadata writers**: id3 for mp3, itunes atoms for m4a, vorbis comments for flac. each container gets its cover art + tags written correctly by the format-appropriate writer; unsupported containers (opus/wav) skip tagging gracefully instead of silently breaking.
- counter now shows `X of Y` during downloads so users can see progress against the full playlist size instead of a bare increment.
- metadata fetch now emits `Fetching track metadata (X of Y)...` every 10 tracks during the pre-download materialization phase so large playlists (700+ tracks) no longer look frozen for the 30-60 seconds of parallel embed fetches.
- artist preview in the song info panel truncates long collaborator lists to `Artist A, Artist B +N` with a tooltip showing the full string, so classical tracks with 4+ performers no longer clip through the fixed-height label.

### Fixed
- stop button now takes effect immediately on large playlists instead of hanging for 10+ seconds. `iter_playlist_tracks` issues serial spclient + per-track metadata requests for playlists over 100 tracks, and the previous `list()` call held the thread for the whole duration before the cancel check could run. materialization now checks `is_cancelled()` between yields so stop preempts mid-fetch.
- cancel-during-parallel-metadata hang: the parallel `/embed/track/{id}` `ThreadPoolExecutor` in `iter_playlist_tracks` previously blocked on `__exit__` waiting for all submitted futures to complete, holding the generator open for 20-30 seconds after the user pressed stop and causing the "download button won't go" symptom on restart. pool lifecycle is now managed via `try/finally` with `shutdown(wait=False, cancel_futures=True)` so pending HTTP fetches get cancelled immediately.
- `RateLimitError` (HTTP 429 from spotify's embed endpoint) is now in the retry decorator's exception list with 4-attempt exponential backoff (1.5× factor), so transient rate limits under concurrent load recover automatically instead of surfacing as a terminal error.
- metadata fetch concurrency dropped from 8 → 4 workers in `iter_playlist_tracks` to stay under spotify's embed-endpoint rate threshold on 700+ track playlists.
- card is now fully opaque (closes #33). the translucent alpha values on the gradient stops (`155` / `191`) made text hard to read when the app sat in front of a bright wallpaper; both stops are now `255`. frameless window stays; only the card content is opacified.
- album row in the song info panel is hidden entirely. spotify's unauthenticated embed endpoints do not expose album name, so the field was always blank; removing it is honest about the limitation instead of showing an empty "Album :" row.

### Changed
- url parsing now accepts `spotify:` URIs (copy-URI from the spotify desktop app), `/intl-xx/` locale-prefixed URLs, and trailing `?si=...` query params. drop-in compatible with the prior HTTPS-only detector; previously-working inputs still work.

### Known limitations
- changing audio format or quality mid-download does not apply to the in-flight download. `ScraperThread` captures the format/quality at construction and the running pool keeps them; new settings take effect on the next download. stop + re-start after changing settings to switch format mid-playlist (no resume, restarts from track 1).

## [2.0.5] - 2026-04-14

### Fixed
- every track in a playlist sharing the same cover art (closes #31). spotify's playlist embed trackList does not include per-track cover urls at all, so every track was falling back to the playlist cover. the download worker now enriches missing cover urls by fetching `/embed/track/{id}` (which has the real `visualIdentity.image`) in parallel with the youtube search, so per-track covers land in the id3 tags at no wall-clock cost.
- release date is now also pulled from the per-track enrichment call when missing, so the `year` id3 tag populates correctly for playlist downloads.

### Added
- track number (id3 `TRCK` / `tracknumber`) is now written to downloaded files using the 1-based playlist position. addresses the broader "no meta tags apart from song name and artist" feedback from #31.

### Notes
- album name and genre remain unavailable in this release because spotify's unauthenticated embed endpoints do not expose them at all. the `/embed/track/{id}` entity's `relatedEntityUri` points at the artist, not the album, and the non-embed track page is a client-rendered spa with no ssr payload. adding those fields would require oauth, which conflicts with the "no account required" model the app is built around.

## [2.0.4] - 2026-04-13

### Added
- parallel track downloads via `ThreadPoolExecutor` with 4 concurrent workers by default (closes #34)
- `MusicScraper.MAX_WORKERS` constant documenting the measured sweet spot
- thread-safe counter and `_failed_tracks` mutation via `threading.Lock`
- `MusicScraper._download_one_track()` extracted as the per-track worker function
- filename collision guard: TOCTOU-safe in-flight file set, de-duped with track id suffix so two tracks that sanitize to the same name don't race
- 13 new tests covering worker count bounds, counter/append atomicity, exception isolation, generator materialization thread-safety, filename collision handling, parallel-mode UI suppression, aggregate progress monotonicity, cancel-before-pool-start behavior, and proof the pool spawns `MAX_WORKERS` concurrent threads under load

### Changed
- `scrape_playlist` materializes the track generator upfront before threading (`iter_playlist_tracks` is a generator and generators are not thread-safe)
- small playlists (under 3 tracks) stay on the single-worker path to preserve single-track UI feel
- cooperative cancel checks at multiple points: before generator materialization, at the top of each worker, and between future completions; queued workers cancel immediately, in-flight downloads finish their current track
- in parallel mode, `song_meta` (UI preview) emits and per-byte `dlprogress_signal` emits are suppressed to prevent label flicker and thumbnail thread spam; progress bar is driven by aggregate completion count
- sequential-mode progress bar still resets per track so single-worker UX is unchanged
- `_parallel_mode` flag is reset after the executor context manager fully exits, avoiding a race where workers still running after a cancel-break could emit single-track UI signals

### Performance
- measured ~4x wall-clock time reduction on 12-track playlists (Apple Silicon M4 Max, macOS). cross-platform builds for Windows, Linux, and macOS ship the same parallel downloader since the concurrency model is pure python + yt-dlp and has no platform-specific code.
- no YouTube or Spotify rate limiting observed at 4-8 concurrent workers during stress testing

## [2.0.3] - 2026-03-31

### Fixed
- cover art now embeds reliably by fetching synchronously in the meta tag writer thread (nested QThread signal delivery was silently failing)
- stop button no longer calls `terminate()`, uses fully cooperative cancellation via cancel event and disables the button during wind-down to prevent double-clicks

### Added
- yt-dlp download resilience: 5 retries, 15s socket timeout, 4 concurrent fragment downloads
- tests for yt-dlp perf options, synchronous cover art fetch, cover art failure handling, and cooperative cancellation

### Changed
- `WritingMetaTagsThread` fetches cover art synchronously with `requests.get()` instead of spawning a nested `DownloadCover` QThread (fixes signal delivery race condition)
- stop button disables during wind-down and re-enables via `thread_finished` signal

## [2.0.2] - 2026-02-01

### Fixed
- resilient embed page extraction handles Spotify A/B testing structure changes (closes #27)
- token extraction tries multiple JSON paths before giving up

### Added
- `_deep_find()` and `_resolve_path()` helpers for flexible JSON traversal
- comprehensive tests for alternative embed page structures
- unit test suite with pytest (43+ tests covering API, downloader, backend)
- comprehensive legal disclaimers across all documentation

### Changed
- split CI workflow into separate tests.yml, lint.yml, webclient.yml for better visibility
- improved thread safety with cooperative cancellation (replaced unsafe terminate())
- added custom exception classes (NetworkError, ExtractionError, RateLimitError)
- added retry decorator with exponential backoff for network requests
- user-friendly error messages in UI for common failure cases

## [2.0.1] - 2026-01-16

### Fixed
- Stop button now properly halts downloads mid-playlist
- Resolved QThread crashes on rapid start/stop
- Improved FFmpeg detection for Homebrew and system installs
- Fixed meta tag writing timing issues
- Fixed download prompt behavior

### Added
- Sponsor buttons to web app
- Homebrew cask now declares FFmpeg dependency

---

## [2.0.0] - 2026-01-15

### Added
- Single track download support (not just playlists)
- Stop button for cancelling downloads mid-progress
- Preview mode banner in webclient explaining desktop app requirement
- Sponsor buttons in desktop app
- Health check endpoint in backend API
- Homebrew cask for macOS installation (see README for install commands)
- Cross-platform release builds (Windows, macOS, Linux) via GitHub Actions
- FFmpeg bundled with pre-built apps (zero-dependency install)
- Redesigned webclient UI matching desktop app aesthetic
- Cold start banner for free-tier backend delays

### Changed
- Switched from spotifydown mirrors to Spotify embed page API (more reliable)
- Migrated backend from AWS Lambda to Render free tier
- Improved FFmpeg detection (homebrew paths, system paths, bundled)
- Modernized Python type annotations throughout codebase
- Enhanced CI/CD with CodeQL scanning, Dependabot, stale automation

### Fixed
- Read-only filesystem error on macOS app bundles
- Threading crashes when stopping downloads
- Meta tags timing issues
- Cover URL extraction with playlist cover fallback
- Cross-platform font compatibility

### Technical
- Python 3.9+ with modern type hints
- Node 20+ for webclient
- PyQt5 desktop app with PyInstaller packaging
- Flask backend with SSE streaming
- Next.js 14 + Tailwind + shadcn/ui webclient

## [1.0.0] - 2024-02-01

### Added
- Initial release
- PyQt5 desktop application for Windows
- Flask backend API with SSE streaming
- Next.js 14 web client
- Multi-provider strategy (Spotify Web API → spotifydown mirrors → yt-dlp)
- ID3 metadata tagging with cover art embedding
- Diagnostic script (`scripts/check_api_status.py`)

### Technical
- Python 3.9+ support
- Node 20+ for webclient
- FFmpeg + yt-dlp for audio processing

[Unreleased]: https://github.com/sunnypatell/sunnify-spotify-downloader/compare/v2.0.8...HEAD
[2.0.8]: https://github.com/sunnypatell/sunnify-spotify-downloader/compare/v2.0.7...v2.0.8
[2.0.7]: https://github.com/sunnypatell/sunnify-spotify-downloader/compare/v2.0.6...v2.0.7
[2.0.6]: https://github.com/sunnypatell/sunnify-spotify-downloader/compare/v2.0.5...v2.0.6
[2.0.5]: https://github.com/sunnypatell/sunnify-spotify-downloader/compare/v2.0.4...v2.0.5
[2.0.4]: https://github.com/sunnypatell/sunnify-spotify-downloader/compare/v2.0.3...v2.0.4
[2.0.3]: https://github.com/sunnypatell/sunnify-spotify-downloader/compare/v2.0.2...v2.0.3
[2.0.2]: https://github.com/sunnypatell/sunnify-spotify-downloader/compare/v2.0.1...v2.0.2
[2.0.1]: https://github.com/sunnypatell/sunnify-spotify-downloader/compare/v2.0.0...v2.0.1
[2.0.0]: https://github.com/sunnypatell/sunnify-spotify-downloader/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/sunnypatell/sunnify-spotify-downloader/releases/tag/v1.0.0
