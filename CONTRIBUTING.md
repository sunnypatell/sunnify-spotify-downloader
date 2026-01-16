<div align="center">

# Contributing to Sunnify

Thanks for considering a contribution. Whether it's a bug report, feature idea, doc fix, or code change, you're welcome here.

</div>

---

## Prerequisites

- **Python**: 3.9+ with pip
- **Node.js**: 20+ with npm
- **FFmpeg**: Required for desktop app audio processing
- **yt-dlp**: Required for YouTube fallback downloads

---

## Quick Start

```bash
# clone your fork
git clone https://github.com/<your-username>/sunnify-spotify-downloader.git
cd sunnify-spotify-downloader

# add upstream remote
git remote add upstream https://github.com/sunnypatell/sunnify-spotify-downloader.git
```

### Desktop App (Python)
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r req.txt
pip install pre-commit && pre-commit install  # install git hooks
python Spotify_Downloader.py
```

### Backend (Flask)
```bash
cd web-app/sunnify-backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

### Webclient (Next.js)
```bash
cd web-app/sunnify-webclient
npm install  # also installs husky hooks
npm run dev
```

---

## Branch Naming

Use conventional prefixes:

| Prefix | Purpose |
|--------|---------|
| `feat/` | New feature |
| `fix/` | Bug fix |
| `docs/` | Documentation only |
| `refactor/` | Code restructuring (no behavior change) |
| `perf/` | Performance improvement |
| `test/` | Adding or updating tests |
| `chore/` | Build, tooling, dependencies |

**Examples:**
```
feat/add-album-download
fix/handle-empty-playlist
docs/update-api-status
refactor/extract-provider-class
```

---

## Commit Message Format

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): description

- bullet point explaining change
- another point if needed
```

### Types
- `feat` - new feature
- `fix` - bug fix
- `docs` - documentation only
- `style` - formatting (no code change)
- `refactor` - code restructuring
- `perf` - performance improvement
- `test` - adding/updating tests
- `build` - build system changes
- `ci` - CI/CD changes
- `chore` - maintenance tasks

### Scopes
- `desktop` - PyQt5 GUI
- `backend` - Flask API
- `webclient` - Next.js frontend
- `providers` - spotifydown_api.py
- `scripts` - diagnostic scripts
- `repo` - repository-wide changes

### Examples
```
feat(webclient): added dark mode toggle

- added theme context provider
- persisted preference to localStorage
- updated all components to use theme tokens
```

```
fix(providers): handled rate limit response from spotify api

- added retry-after header parsing
- implemented exponential backoff
```

---

## Code Quality

### Python
```bash
# lint
ruff check .

# format
ruff format .

# both (auto-fix)
ruff check . --fix && ruff format .
```

### Webclient
```bash
cd web-app/sunnify-webclient

# lint
npm run lint

# type check
npm run typecheck

# format
npm run format

# check format without writing
npm run format:check
```

### Pre-commit Hooks

Hooks run automatically on `git commit`:
- **Python**: ruff lint + format via pre-commit
- **Webclient**: eslint + prettier via husky/lint-staged

To run manually:
```bash
# python
pre-commit run --all-files

# webclient
cd web-app/sunnify-webclient && npx lint-staged
```

---

## Pull Request Workflow

1. Create a branch from `main`
   ```bash
   git checkout main && git pull upstream main
   git checkout -b feat/your-feature
   ```

2. Make changes and commit
   ```bash
   git add -A
   git commit -m "feat(scope): description"
   ```

3. Rebase on latest main before pushing
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

4. Push and open PR
   ```bash
   git push -u origin HEAD
   ```

5. Fill out the PR template completely

6. Address review feedback with additional commits (don't force-push during review)

---

## Style Guidelines

### Python
- Target Python 3.9+ for compatibility
- Use type hints for function signatures
- Prefer explicit errors over silent failures
- Reuse `requests.Session()` for HTTP calls
- Follow ruff's formatting (4-space indent, 100 char line)

### TypeScript/React
- Use functional components with hooks
- Prefer TypeScript strict mode patterns
- Use environment variables for configuration
- Follow prettier's formatting (2-space indent, no semicolons)

### General
- Keep PRs focused and small
- Update docs when changing behavior
- Avoid unrelated refactors in the same PR
- Write descriptive commit messages

---

## Security and Legal

**Do not** open public issues for security vulnerabilities. Follow the process in [SECURITY.md](SECURITY.md).

This project is for **educational use only**. See [LICENSE](LICENSE) for details.

---

## Code of Conduct

By participating, you agree to abide by the [Code of Conduct](CODE_OF_CONDUCT.md).
