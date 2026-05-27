# Homebrew Cask for Sunnify
# Install:
#   brew tap sunnypatell/sunnify https://github.com/sunnypatell/sunnify-spotify-downloader
#   brew install --cask sunnify

cask "sunnify" do
  version "2.0.7"
  sha256 "119545496a7ecf4d6153571dbe65730ae6919c54b669a672c1363a8308137b83"

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
