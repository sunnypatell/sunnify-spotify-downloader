# Homebrew Cask for Sunnify
# Install:
#   brew tap sunnypatell/sunnify https://github.com/sunnypatell/sunnify-spotify-downloader
#   brew install --cask sunnify

cask "sunnify" do
  version "2.0.12"
  sha256 "af47913e1227cd65aabfc52dce5e7683239fe183d710d9b8ba80dec04147926f"

  url "https://github.com/sunnypatell/sunnify-spotify-downloader/releases/download/v#{version}/Sunnify-macOS.zip"
  name "Sunnify"
  desc "Download Spotify playlists to local MP3s with artwork and tags"
  homepage "https://github.com/sunnypatell/sunnify-spotify-downloader"

  app "Sunnify.app"

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

    Transparency note: Sunnify is ad-hoc signed, not notarized (notarization
    requires a paid Apple Developer membership; this is an unfunded student
    project). The install step above already removed macOS quarantine, so
    the app opens normally. Verify the build's provenance any time with:
      gh attestation verify Sunnify-macOS.zip --repo sunnypatell/sunnify-spotify-downloader

    Educational use only. Ensure compliance with copyright laws.
  EOS
end
