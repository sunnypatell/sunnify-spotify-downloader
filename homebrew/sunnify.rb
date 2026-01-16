# Homebrew Cask for Sunnify
# To install: brew install --cask sunnify
#
# Note: This is a template. To publish to Homebrew, either:
# 1. Submit to homebrew-cask (requires notarization)
# 2. Create your own tap: brew tap sunnypatell/sunnify
#
# For unsigned apps, users need to run after installation:
#   sudo xattr -cr /Applications/Sunnify.app

cask "sunnify" do
  version "2.0.0"
  sha256 :no_check  # Update with actual SHA256 after release

  url "https://github.com/sunnypatell/sunnify-spotify-downloader/releases/download/v#{version}/Sunnify-macOS.zip"
  name "Sunnify"
  desc "Download Spotify playlists to local MP3s with artwork and tags"
  homepage "https://github.com/sunnypatell/sunnify-spotify-downloader"

  # Requires FFmpeg for audio conversion
  depends_on formula: "ffmpeg"

  app "Sunnify.app"

  postflight do
    # Remove quarantine attribute for unsigned app
    system_command "/usr/bin/xattr",
                   args: ["-cr", "#{appdir}/Sunnify.app"],
                   sudo: true
  end

  uninstall quit: "com.sunnypatel.sunnify"

  zap trash: [
    "~/Library/Application Support/Sunnify",
    "~/Library/Preferences/com.sunnypatel.sunnify.plist",
    "~/Library/Caches/com.sunnypatel.sunnify",
  ]

  caveats <<~EOS
    Sunnify requires FFmpeg for audio conversion.
    Install it with: brew install ffmpeg

    If you see "app is damaged" or "unidentified developer" errors:
      sudo xattr -cr /Applications/Sunnify.app

    Educational use only. Ensure compliance with copyright laws.
  EOS
end
