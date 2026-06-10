# Security Policy

> **⚠️ Educational Project Notice**
>
> **Sunnify is a student portfolio project** developed for educational and demonstration purposes only. This security policy covers vulnerabilities in the codebase itself, not the legality of how the software might be used. For legal terms and disclaimers, see [DISCLAIMER.md](DISCLAIMER.md).

---

## Supported Versions

We currently support the active development branch and the latest 2.x release line.

| Version | Supported |
| ------: | :-------: |
| main    | ✅        |
| 2.0.9   | ✅        |
| 2.0.8   | ❌        |
| 2.0.7   | ❌        |
| < 2.0.7 | ❌        |

## Reporting a Vulnerability

Preferred: use [GitHub private vulnerability reporting](https://github.com/sunnypatell/sunnify-spotify-downloader/security/advisories/new) ("Report a vulnerability" on the Security tab). It keeps the report private, threads the discussion, and produces a CVE-ready advisory if one is warranted.

Alternatively, email `sunnypatel124555@gmail.com` with the subject line `[SECURITY] <short description>`.

Include:
- A clear description of the issue and potential impact
- Steps or a minimal proof of concept to reproduce
- Affected versions or commit SHAs, if known

Acknowledgement SLA: within 3 business days.
Status updates: at least weekly until resolution.

Coordinated disclosure is appreciated. If a fix is accepted, we will work with you on timing and credit.

---

## Release integrity

Starting with 2.0.8, every release attaches signed build provenance + SBOM
attestations so users can verify what they downloaded came from this repository,
from a specific source commit, built by the workflow they can inspect.

### What's attached to every release

| Asset | What it is |
| :--- | :--- |
| `Sunnify-Windows.exe` / `Sunnify-Linux` / `Sunnify-macOS.zip` | Platform binaries |
| `<binary>.sigstore.json` | Offline-verifiable sigstore attestation bundle for each binary |
| `sunnify-sbom.cdx.json` | CycloneDX SBOM describing the delivered artifacts |
| `sunnify-vX.Y.Z-source.tar.gz` | `git archive` of the source at the release commit |
| `checksums.txt` | SHA256 of every asset, in `sha256sum -c` format |

### Four independent verification paths

**1. Plain checksums** — no extra tooling. Download `checksums.txt` and the
   asset you care about, then:

   ```bash
   sha256sum -c checksums.txt --ignore-missing
   ```

**2. SLSA Build L3 provenance** — proves the binary came from a specific
   commit in this repo, built by the dedicated
   [`release-build.yml`](.github/workflows/release-build.yml) reusable
   workflow in an isolated runner. The reusable-workflow split is what makes
   this Build L3 rather than L2: the build instructions are isolated from
   the workflow that dispatched them
   ([GitHub's L3 guide](https://docs.github.com/actions/security-guides/using-artifact-attestations-and-reusable-workflows-to-achieve-slsa-v1-build-level-3)).
   Signed with the runner's short-lived Sigstore identity and logged to the
   Rekor public transparency log. Requires the GitHub CLI:

   ```bash
   gh attestation verify Sunnify-Linux \
     --repo sunnypatell/sunnify-spotify-downloader \
     --signer-workflow sunnypatell/sunnify-spotify-downloader/.github/workflows/release-build.yml
   ```

   (`--signer-workflow` is optional but pins the trusted builder; without it
   you still verify repo + source commit.)

**3. SBOM attestation** — proves the SBOM published alongside the release
   was produced from those exact binaries (binary digest -> SBOM digest
   binding), signed by the same Sigstore chain. Same command, same repo;
   `gh attestation verify` accepts the binary and finds both predicate
   types automatically.

**4. Offline bundle** — every binary ships with its `<name>.sigstore.json`
   attestation bundle as a release asset, so verification works without
   GitHub's attestation API in the loop:

   ```bash
   gh attestation verify Sunnify-Linux \
     --repo sunnypatell/sunnify-spotify-downloader \
     --bundle Sunnify-Linux.sigstore.json
   ```

### Supply-chain practices in the build

- **Hash-locked build inputs.** Release builds install python dependencies
  (including PyInstaller itself) with `pip install --require-hashes` against
  `requirements-build.txt`, a universal lockfile with a SHA256 for every
  wheel on every platform. A compromised PyPI release or poisoned pip cache
  fails closed instead of shipping inside the binary. (The test matrix
  deliberately keeps floating ranges from `req.txt` so upstream breakage
  surfaces on a red test before it surfaces in a release build.)
- **FFmpeg pinned + SHA256-verified.** The build refuses to extract an
  archive whose SHA256 doesn't match a value embedded in the workflow file,
  so a CDN swap or compromised mirror aborts the build instead of silently
  shipping the wrong binary.
- **All third-party GitHub Actions SHA-pinned** with a trailing `# vX.Y.Z`
  comment. A tag re-target cannot silently swap an action's code. Dependabot
  (grouped, monthly, 7-day cooldown) keeps the pins fresh so they never rot.
- **Per-job least-privilege permissions.** Build jobs are `contents: read`
  only; `attestations: write` + `id-token: write` exist only where
  attestations are produced.
- **Workflow static analysis.** actionlint + [zizmor](https://docs.zizmor.sh/)
  run in CI on every workflow change (template injection, unpinned actions,
  credential persistence, cache poisoning, ...).
- **Egress telemetry.** Release jobs run
  [harden-runner](https://github.com/step-security/harden-runner) in audit
  mode, recording every outbound connection from the build. Audit (not
  block) is deliberate: block-mode allowlists are a known false-positive
  maintenance trap, and a runner-resident agent is a detection layer, not a
  security boundary.
- **Dependency review on pull requests.** A PR that introduces a new
  dependency with a known high-severity CVE is blocked at the PR status
  check before it can merge.
- **osv-scanner release gate.** The release pipeline refuses to upload
  binaries whose SBOM contains a known CVE.
- **CodeQL** runs weekly + on every PR, and
  [OpenSSF Scorecard](https://scorecard.dev/viewer/?uri=github.com/sunnypatell/sunnify-spotify-downloader)
  re-scores the repo's supply-chain posture weekly.

### What we explicitly do not have

- **Code-signing certificates** (macOS notarization / Windows Authenticode).
  Both require paid issuer accounts; the project is unfunded. The macOS app
  is ad-hoc signed with a build-time-verified seal: installing via the
  Homebrew tap is frictionless (the cask strips quarantine post-install,
  after Homebrew has verified the archive's SHA256 against the cask), and
  direct downloads use the System Settings "Open Anyway" flow documented in
  the README. Windows users see SmartScreen "unknown publisher" on first
  launch.
- **Bit-for-bit reproducible builds.** Release builds set PyInstaller's two
  documented determinism knobs (`PYTHONHASHSEED`, `SOURCE_DATE_EPOCH`) and
  hash-lock all build inputs, which removes the gratuitous variance - but
  macOS signing and bootloader variance mean independent rebuilds are still
  not byte-identical, and we don't claim otherwise. The provenance
  attestation is the compensating control: it binds each binary to its
  source commit and builder.
- **Fuzzing.** OSS-Fuzz/ClusterFuzzLite target parsing-heavy attack surface;
  this app's parsers are exercised against live services in the test suite
  and a fuzz harness would be maintenance theater for its threat model.

---

## Legal Note

This project is provided "as is" without warranty of any kind. It is an educational demonstration and is not intended for unauthorized downloading of copyrighted content. The developer assumes no liability for how this software is used. See [DISCLAIMER.md](DISCLAIMER.md) for complete legal terms.
