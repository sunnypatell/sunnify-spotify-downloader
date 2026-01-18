# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Unit test suite with pytest (43 tests covering API, downloader, backend)
- Comprehensive legal disclaimers across all documentation

### Changed
- Split CI workflow into separate tests.yml, lint.yml, webclient.yml for better visibility
- Improved thread safety with cooperative cancellation (replaced unsafe terminate())
- Added custom exception classes (NetworkError, ExtractionError, RateLimitError)
- Added retry decorator with exponential backoff for network requests
- User-friendly error messages in UI for common failure cases

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

[Unreleased]: https://github.com/sunnypatell/sunnify-spotify-downloader/compare/v2.0.1...HEAD
[2.0.1]: https://github.com/sunnypatell/sunnify-spotify-downloader/compare/v2.0.0...v2.0.1
[2.0.0]: https://github.com/sunnypatell/sunnify-spotify-downloader/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/sunnypatell/sunnify-spotify-downloader/releases/tag/v1.0.0
