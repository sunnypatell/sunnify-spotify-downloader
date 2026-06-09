# Homebrew Cask for Sunnify
# Install:
#   brew tap sunnypatell/sunnify https://github.com/sunnypatell/sunnify-spotify-downloader
#   brew install --cask sunnify

cask "sunnify" do
  version "2.0.9"
  sha256 "8b1dff9b5e941b1a655d0901d076e783f2cbd71aecfd4c26ad15aa25eea48c14"

  url "https://github.com/sunnypatell/sunnify-spotify-downloader/releases/download/v#{version}/Sunnify-macOS.zip"
  name "Sunnify"
  desc "Download Spotify playlists to local MP3s with artwork and tags"
  homepage "https://github.com/sunnypatell/sunnify-spotify-downloader"

  app "Sunnify.app"

  uninstall quit: "com.sunnypatel.sunnify"

  zap trash: [
    "~/Library/Application Support/Sunnify",
    "~/Library/Preferences/com.sunnypatel.sunnify.plist",
    "~/Library/Caches/com.sunnypatel.sunnify",
  ]

  caveats <<~EOS
    FFmpeg is bundled with the app - no separate installation needed.

    After installation, run this command to remove macOS quarantine:
      sudo xattr -cr /Applications/Sunnify.app

    Educational use only. Ensure compliance with copyright laws.
  EOS
end
