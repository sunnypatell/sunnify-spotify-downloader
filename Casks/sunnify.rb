# Homebrew Cask for Sunnify
# Install:
#   brew tap sunnypatell/sunnify https://github.com/sunnypatell/sunnify-spotify-downloader
#   brew install --cask sunnypatell/sunnify/sunnify

cask "sunnify" do
  arch intel: "-Intel"

  version "2.5.0"
  # both shas are recomputed and rewritten by the release workflow
  sha256 arm:   "557de8604023d7debcb55ea0471a8c4554dbc03ac395964600ec1f8ff672295b",
         intel: "350ab0b244b41768fce3b1cbb31607cd7b0da9cfa3ddea691b42cdb9710ceaa7"

  url "https://github.com/sunnypatell/sunnify-spotify-downloader/releases/download/v#{version}/Sunnify-macOS#{arch}.zip"
  name "Sunnify"
  desc "Download Spotify playlists to local MP3s with artwork and tags"
  homepage "https://github.com/sunnypatell/sunnify-spotify-downloader"

  depends_on :macos

  app "Sunnify.app"
  # headless CLI: the app binary dispatches on argv, so one symlink gives
  # `sunnify download/info/status/config/doctor` on PATH
  binary "#{appdir}/Sunnify.app/Contents/MacOS/Sunnify", target: "sunnify"

  # App is ad-hoc signed (no paid Apple cert); brew already SHA256-verified
  # the archive, so strip quarantine to make first launch just work.
  # {{appdir}} is expanded by brew at install time (step args are literal
  # otherwise), so this follows a custom --appdir instead of assuming /Applications.
  postflight_steps do
    run "/usr/bin/xattr",
        args:         ["-r", "-d", "com.apple.quarantine", "{{appdir}}/Sunnify.app"],
        must_succeed: false
  end

  uninstall quit: "com.sunnypatel.sunnify"

  zap trash: [
    "~/Library/Application Support/Sunnify",
    "~/Library/Caches/com.sunnypatel.sunnify",
    "~/Library/Preferences/com.sunnypatel.sunnify.plist",
  ]

  caveats <<~EOS
    FFmpeg is bundled with the app - no separate installation needed.

    Headless CLI: `sunnify --help` (same engine and settings as the app).

    Transparency note: Sunnify is ad-hoc signed, not notarized (notarization
    requires a paid Apple Developer membership; this is an unfunded student
    project). The install step above already removed macOS quarantine, so
    the app opens normally. Verify the build's provenance any time with:
      gh attestation verify Sunnify-macOS#{arch}.zip --repo sunnypatell/sunnify-spotify-downloader

    Educational use only. Ensure compliance with copyright laws.
  EOS
end
