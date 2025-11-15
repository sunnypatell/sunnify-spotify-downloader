<div align="center">

# Contributing to Sunnify

Thanks for considering a contribution. Whether it’s a bug report, feature idea, doc fix, or code change, you’re welcome here.

</div>

---

## Ways to Contribute

### 1) Report bugs

Include a clear description, steps to reproduce, expected vs actual behavior, and logs or screenshots if helpful.

### 2) Propose features

Explain the use case, why it adds value, and any example flows or mockups.

### 3) Submit changes

1. Fork the repository, then clone your fork
   ```bash
   git clone https://github.com/<your-username>/sunnify-spotify-downloader.git

2. Add the upstream remote
   ```bash
   cd sunnify-spotify-downloader
   git remote add upstream https://github.com/sunnypatell/sunnify-spotify-downloader.git
   ```
3. Create a branch for your change
   ```bash
   git checkout -b feat/short-description
   # or fix/short-description, docs/short-description
   ```
4. Set up the project locally (pick the parts you need)

   Desktop app (Python):
   ```bash
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r req.txt
   python Spotify_Downloader.py
   ```

   Backend (Flask):
   ```bash
   cd web-app/sunnify-backend
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   python app.py
   ```

   Frontend (Next.js):
   ```bash
   cd web-app/sunnify-webclient
   npm install
   npm run dev
   ```

5. Commit with a clear message
   ```bash
   git add -A
   git commit -m "feat(web): add env-based API base url"
   ```
6. Rebase on latest main if needed
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```
7. Push and open a Pull Request
   ```bash
   git push -u origin HEAD
   ```

---

## Style and Guidelines

- Keep PRs focused and small where possible
- Write descriptive commit messages
- Update or add docs when changing behavior
- Match the existing code style in each area
- Avoid unrelated refactors in the same PR

Python tips:
- Target Python 3.8+ for new code
- Prefer explicit errors over silent failures
- Use `requests.Session()` reuse where applicable

Web tips:
- Use env vars such as `NEXT_PUBLIC_API_BASE` for endpoints
- Avoid hardcoding URLs when an env option will do

---

## Security and Legal

Please do not open public issues for security vulnerabilities. Instead, follow the process in [SECURITY.md](SECURITY.md).

This project is for educational use. See [LICENSE](LICENSE) and the root README for details.

---

## Code of Conduct

By participating, you agree to abide by the [Code of Conduct](CODE_OF_CONDUCT.md).
