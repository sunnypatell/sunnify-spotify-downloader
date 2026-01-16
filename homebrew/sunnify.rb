# Homebrew Cask for Sunnify
# Install: brew install --cask sunnypatell/sunnify/sunnify

cask "sunnify" do
  version "2.0.0"
  sha256 "8b264436d644e42dc82c8a3e8fe79ea9e1003dfde9482c225e5a03f60ac89607"

  url "https://github.com/sunnypatell/sunnify-spotify-downloader/releases/download/v#{version}/Sunnify-macOS.zip"
  name "Sunnify"
  desc "Download Spotify playlists to local MP3s with artwork and tags"
  homepage "https://github.com/sunnypatell/sunnify-spotify-downloader"

  app "Sunnify.app"

  postflight do
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
    FFmpeg is bundled with the app - no separate installation needed.

    If you see "app is damaged" or "unidentified developer" errors,
    the postflight script should have handled this automatically.
    If not, run: sudo xattr -cr /Applications/Sunnify.app

    Educational use only. Ensure compliance with copyright laws.
  EOS
end
