#!/bin/sh
# Sunnify installer (macOS + Linux) - safe to pipe: curl -fsSL <raw-url> | sh
#
# Design rules (AI agents drive this):
#   - zero prompts, zero sudo, no TTY reads: everything is user-scope
#   - downloads come from GitHub release assets (SHA256-verified against the
#     release's checksums.txt before anything is installed)
#   - idempotent: re-running replaces the previous install
#
# macOS note: prefer `brew install --cask sunnify` (tap in the README); this
# script is the no-Homebrew fallback and does the same quarantine clearing.
set -eu

REPO="sunnypatell/sunnify-spotify-downloader"
BASE="https://github.com/$REPO/releases/latest/download"
BIN_DIR="$HOME/.local/bin"
OS="$(uname -s)"
ARCH="$(uname -m)"

say() { printf '%s\n' "$*"; }
fail() { printf 'error: %s\n' "$*" >&2; exit 1; }

case "$OS" in
  Darwin)
    case "$ARCH" in
      arm64) ASSET="Sunnify-macOS.zip" ;;
      x86_64) ASSET="Sunnify-macOS-Intel.zip" ;;
      *) fail "unsupported macOS architecture: $ARCH" ;;
    esac
    SHATOOL="shasum -a 256"
    ;;
  Linux)
    case "$ARCH" in
      x86_64) ASSET="Sunnify-Linux" ;;
      *) fail "unsupported Linux architecture: $ARCH (releases ship x86_64)" ;;
    esac
    SHATOOL="sha256sum"
    ;;
  *) fail "unsupported OS: $OS (use install.ps1 on Windows)" ;;
esac

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

say "downloading $ASSET (latest release)..."
curl -fsSL -o "$TMP/$ASSET" "$BASE/$ASSET"
curl -fsSL -o "$TMP/checksums.txt" "$BASE/checksums.txt"

EXPECTED="$(grep " $ASSET\$" "$TMP/checksums.txt" | awk '{print $1}')"
[ -n "$EXPECTED" ] || fail "checksums.txt has no entry for $ASSET"
ACTUAL="$($SHATOOL "$TMP/$ASSET" | awk '{print $1}')"
[ "$ACTUAL" = "$EXPECTED" ] || fail "SHA256 mismatch for $ASSET (got $ACTUAL, want $EXPECTED)"
say "checksum verified"

mkdir -p "$BIN_DIR"
if [ "$OS" = "Darwin" ]; then
  APP_DIR="$HOME/Applications"
  mkdir -p "$APP_DIR"
  rm -rf "$APP_DIR/Sunnify.app"
  unzip -oq "$TMP/$ASSET" -d "$APP_DIR"
  # ad-hoc signed app: clearing quarantine here is what the Homebrew cask
  # does post-install, so first launch never hits the Gatekeeper dialog
  xattr -r -d com.apple.quarantine "$APP_DIR/Sunnify.app" 2>/dev/null || true
  ln -sf "$APP_DIR/Sunnify.app/Contents/MacOS/Sunnify" "$BIN_DIR/sunnify"
  say "installed: $APP_DIR/Sunnify.app (GUI) + $BIN_DIR/sunnify (CLI)"
else
  install -m 0755 "$TMP/$ASSET" "$BIN_DIR/sunnify"
  say "installed: $BIN_DIR/sunnify (run with no arguments for the GUI)"
fi

case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *)
    say ""
    say "note: $BIN_DIR is not on your PATH. add this to your shell profile:"
    say "  export PATH=\"\$HOME/.local/bin:\$PATH\""
    ;;
esac

say ""
say "try: sunnify --help"
