# Releasing Sunnify

The complete runbook for cutting a release. The pipeline does the heavy
lifting; this file exists so a release never depends on memory.

## 0. Preconditions

- On `main`, clean tree, tests green
- `gh` authenticated as the repo owner

## 1. Bump the version everywhere

Don't trust a fixed file list - grep for the current version first, because a
location has been missed before:

```bash
grep -rnE "2\.0\.10|2, 0, 10" --include="*.py" --include="*.toml" \
  --include="*.spec" --include="*.txt" --include="*.md" .
```

Known locations: `version.txt` (bare + comma form), `pyproject.toml`,
`Spotify_Downloader.py` `__version__`, `Template.py` UI label,
`Sunnify.spec` (BOTH the `filevers`/`prodvers` numeric tuples AND the
string fields - the tuples were historically left stale),
`API_STATUS.md`, `web-app/sunnify-backend/app.py`, `SECURITY.md`
supported-versions table (shift rows).

NOT the version: `req.txt` pins, npm lockfiles, `Casks/sunnify.rb`
(the release workflow bumps the cask automatically - never touch it by hand).

## 2. Changelog + commit

- Add `[X.Y.Z] - DATE` under `[Unreleased]` in `CHANGELOG.md`
  (Keep-a-Changelog format, `### Added/Fixed/Changed/Notes`), add the
  compare link at the bottom, repoint `[Unreleased]`
- Commit: `feat(desktop): vX.Y.Z - <summary> (closes #NN, ...)`, push main

## 3. Tag + draft release

```bash
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin vX.Y.Z
gh release create vX.Y.Z --draft --notes-file /tmp/notes-vX.Y.Z.md
```

DRAFT first, always. The build workflow uploads assets to the draft and
publishes it at the end. Publishing before assets exist means users see an
empty release, and (if immutable releases are enabled) publishing freezes
the asset list permanently - a published-empty release cannot be fixed.

Release-notes house style: `## what's changed`, lowercase `### added/fixed`
sections, bold lead phrase per bullet with `(closes #NN)`, `---`, the
standing "verifying this release" + "install via homebrew (macos)" footers,
`**full changelog**:` compare link. Write with `--notes-file`, never inline
heredoc (shell-escaped backticks leak).

## 4. Build + publish

```bash
gh workflow run release.yml -f tag=vX.Y.Z
gh run watch
```

What the pipeline does, in order: validates the tag shape, builds all three
platforms via the `release-build.yml` reusable workflow (hash-locked deps,
SHA-verified FFmpeg, deterministic-build env vars, per-binary SLSA L3
provenance attestation signed inside the reusable workflow), generates and
attests the SBOM, blocks on osv-scanner CVEs, builds and attests the source
tarball, writes `checksums.txt`, uploads everything (including the
`*.sigstore.json` offline bundles) to the draft, publishes it, splices the
run's attestation links into the release notes, then recomputes and pushes
the Homebrew cask bump to main.

## 5. After the run

```bash
git pull   # picks up the cask auto-update commit
```

Reply to any issues the release closes (house style: `@user shipped a fix in
[vX.Y.Z](link)`, "what was happening" / "what changes" headers, honest
caveat, upgrade nudge).

## Dry-running the pipeline

Test end-to-end without touching main or users:

```bash
git tag -a vX.Y.Z-rc.1 -m "pipeline test" && git push origin vX.Y.Z-rc.1
gh release create vX.Y.Z-rc.1 --draft --notes "pipeline dry-run"
gh workflow run release.yml --ref <branch> -f tag=vX.Y.Z-rc.1 -f dry_run=true
```

`dry_run` skips the cask job entirely and leaves the release as a draft.
Delete the draft + tag afterwards.

## Fixing a botched release

If the release is still a DRAFT: re-dispatch the workflow on the same tag;
the upload job is idempotent (delete-then-upload).

If the release is PUBLISHED: ship a patch release (vX.Y.Z+1). Don't replace
binaries under a published tag - users and the cask have already seen the
old digests, and re-running on a published tag is the exact mutable-release
pattern the attestation work exists to kill.

## Maintenance that is NOT per-release

- **FFmpeg pins**: every few months, bump procedure documented at the top of
  `.github/workflows/release-build.yml`
- **Dependency pins**: Dependabot opens one grouped PR per ecosystem per
  month (action SHAs, python, npm); merging it is the whole job. The
  `requirements-build.txt` hash lock regenerates with:
  `uv pip compile requirements-build.in --universal --generate-hashes -o requirements-build.txt`
- Everything else (CodeQL, Scorecard, zizmor/actionlint, stale-bot) is
  scheduled and input-free
