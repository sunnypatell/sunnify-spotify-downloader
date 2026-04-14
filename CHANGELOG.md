# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/sunnypatell/sunnify-spotify-downloader/compare/v2.0.4...HEAD
[2.0.4]: https://github.com/sunnypatell/sunnify-spotify-downloader/compare/v2.0.3...v2.0.4
[2.0.3]: https://github.com/sunnypatell/sunnify-spotify-downloader/compare/v2.0.2...v2.0.3
[2.0.2]: https://github.com/sunnypatell/sunnify-spotify-downloader/compare/v2.0.1...v2.0.2
[2.0.1]: https://github.com/sunnypatell/sunnify-spotify-downloader/compare/v2.0.0...v2.0.1
[2.0.0]: https://github.com/sunnypatell/sunnify-spotify-downloader/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/sunnypatell/sunnify-spotify-downloader/releases/tag/v1.0.0
