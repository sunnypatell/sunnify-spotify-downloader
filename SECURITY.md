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
| 2.0.8   | ✅        |
| 2.0.7   | ❌        |
| 2.0.6   | ❌        |
| < 2.0.6 | ❌        |

## Reporting a Vulnerability

Please report security issues privately by emailing `sunnypatell124555@gmail.com` with the subject line `[SECURITY] <short description>`.

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
| `sunnify-sbom.cdx.json` | CycloneDX SBOM describing the delivered artifacts |
| `sunnify-vX.Y.Z-source.tar.gz` | `git archive` of the source at the release commit |
| `checksums.txt` | SHA256 of every asset, in `sha256sum -c` format |

### Three independent verification paths

**1. Plain checksums** — no extra tooling. Download `checksums.txt` and the
   asset you care about, then:

   ```bash
   sha256sum -c checksums.txt --ignore-missing
   ```

**2. SLSA L3 build provenance** — proves the binary came from a specific
   commit in this repo, built by this workflow, in an isolated runner.
   Signed with the runner's short-lived Sigstore identity and logged to the
   Rekor public transparency log. Requires the GitHub CLI:

   ```bash
   gh attestation verify Sunnify-Linux \
     --repo sunnypatell/sunnify-spotify-downloader
   ```

**3. SBOM attestation** — proves the SBOM published alongside the release
   was produced from those exact binaries (binary digest -> SBOM digest
   binding), signed by the same Sigstore chain. Same command, same repo;
   `gh attestation verify` accepts the binary and finds both predicate
   types automatically.

### Supply-chain practices in the build

- **FFmpeg pinned + SHA256-verified.** The build refuses to extract an
  archive whose SHA256 doesn't match a value embedded in the workflow file,
  so a CDN swap or compromised mirror aborts the build instead of silently
  shipping the wrong binary.
- **All third-party GitHub Actions SHA-pinned** with a trailing `# vX.Y.Z`
  comment. A tag re-target cannot silently swap an action's code.
- **Per-job least-privilege permissions.** Build jobs are `contents: read`
  only; only the upload job has `attestations: write` + `id-token: write`.
- **Dependency review on pull requests.** A PR that introduces a new
  dependency with a known high-severity CVE is blocked at the PR status
  check before it can merge.
- **CodeQL** runs weekly + on every PR.

### What we explicitly do not have

- **Code-signing certificates** (macOS notarization / Windows Authenticode).
  Both require paid issuer accounts; the project is unfunded. macOS users
  bypass Gatekeeper with the `sudo xattr -cr /Applications/Sunnify.app`
  command documented in the install instructions; Windows users see
  SmartScreen "unknown publisher" on first launch.
- **Reproducible builds.** PyInstaller is non-deterministic by default and
  making it deterministic for this app is a research project, not a
  weekend task. The provenance attestation still binds each binary to the
  source commit, but two builds of the same commit will not produce
  byte-identical artifacts.

---

## Legal Note

This project is provided "as is" without warranty of any kind. It is an educational demonstration and is not intended for unauthorized downloading of copyrighted content. The developer assumes no liability for how this software is used. See [DISCLAIMER.md](DISCLAIMER.md) for complete legal terms.
