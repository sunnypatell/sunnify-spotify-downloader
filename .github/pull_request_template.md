<div align="center">

# Pull Request

</div>

## Summary

Describe the change and the user-facing impact.

## Type of change

- [ ] feat (new feature)
- [ ] fix (bug fix)
- [ ] docs (documentation only)
- [ ] perf (performance)
- [ ] chore (build, tooling, refactors)

## Scope (select all that apply)

- [ ] Desktop (PyQt5 GUI)
- [ ] Backend (Flask API)
- [ ] Webclient (Next.js)
- [ ] Core Providers (`spotifydown_api.py`)
- [ ] Scripts/Diagnostics (`scripts/check_api_status.py`)
- [ ] Documentation

## Linked issues

Closes #<id> (or) Related to #<id>

## Details

What changed and why? Include UX notes, endpoint changes, and config if relevant.

## How I tested this

- OS and versions (Windows/macOS/Linux):
- Python / pip:
- Node / npm:
- FFmpeg / yt-dlp:
- Commands run:

```bash
# examples
python scripts/check_api_status.py
python Spotify_Downloader.py
cd web-app/sunnify-backend && python app.py
cd web-app/sunnify-webclient && npm run dev
```

Screenshots or console output (if applicable):

## Breaking changes

- [ ] None
- If any, describe the break and migration steps

## Risks and rollbacks

Call out risk areas and how to revert if needed.

## Checklist

- [ ] I ran `python scripts/check_api_status.py` or validated relevant endpoints
- [ ] FFmpeg is on PATH (`ffmpeg -version`) and `yt-dlp` is up to date when desktop is affected
- [ ] Webclient changes use `NEXT_PUBLIC_API_BASE` instead of hardcoded URLs
- [ ] Backend changes documented in README or API docs
- [ ] Tests or manual validation steps included
- [ ] Docs updated where behavior changed (README/CONTRIBUTING/etc.)
- [ ] I read the SECURITY and Legal sections to avoid adding risky functionality