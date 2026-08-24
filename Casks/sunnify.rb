# Homebrew Cask for Sunnify
# Install:
#   brew tap sunnypatell/sunnify https://github.com/sunnypatell/sunnify-spotify-downloader
#   brew install --cask sunnify

cask "sunnify" do
  arch arm: "", intel: "-Intel"

  version "2.4.0"
  # both shas are recomputed and rewritten by the release workflow
  sha256 arm:   "8d7d03b5c4656b2bacf2dbb65ccfe8b684360f86708335226be1948fdc09a742",
         intel: "949e64ac83d57ffcb7d642df492137886031739d26d12839d11bf880c7efe48a"

  url "https://github.com/sunnypatell/sunnify-spotify-downloader/releases/download/v#{version}/Sunnify-macOS#{arch}.zip"
  name "Sunnify"
  desc "Download Spotify playlists to local MP3s with artwork and tags"
  homepage "https://github.com/sunnypatell/sunnify-spotify-downloader"

  app "Sunnify.app"
  # headless CLI: the app binary dispatches on argv, so one symlink gives
  # `sunnify download/info/status/config/doctor` on PATH
  binary "#{appdir}/Sunnify.app/Contents/MacOS/Sunnify", target: "sunnify"

  # App is ad-hoc signed (no paid Apple cert); brew already SHA256-verified
  # the archive, so strip quarantine to make first launch just work.
  postflight do
    system_command "/usr/bin/xattr",
                   args: ["-r", "-d", "com.apple.quarantine", "#{appdir}/Sunnify.app"],
                   must_succeed: false
  end

  uninstall quit: "com.sunnypatel.sunnify"

  zap trash: [
    "~/Library/Application Support/Sunnify",
    "~/Library/Preferences/com.sunnypatel.sunnify.plist",
    "~/Library/Caches/com.sunnypatel.sunnify",
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
