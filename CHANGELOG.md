# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- GitHub Actions CI workflow for Python (ruff) and webclient (lint, typecheck, build)
- CodeQL security scanning (weekly + on push/PR)
- Stale issue/PR automation (60 days → stale, +7 → close)
- Dependabot for automated dependency updates (pip, npm, github-actions)
- CODEOWNERS for automatic review requests
- EditorConfig for consistent editor settings
- Pre-commit hooks for Python (ruff)
- Husky + lint-staged for webclient pre-commit hooks
- Prettier configuration for webclient
- Question issue template

### Changed
- Enhanced ESLint config with warning rules
- Improved PR template with organized checklist sections
- Modernized Python type annotations (dict vs Dict, X | None vs Optional)
- Updated CONTRIBUTING.md with tooling setup instructions

### Fixed
- Bare except clauses replaced with specific exception types
- Exception chaining added where missing

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

[Unreleased]: https://github.com/sunnypatell/sunnify-spotify-downloader/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/sunnypatell/sunnify-spotify-downloader/releases/tag/v1.0.0
