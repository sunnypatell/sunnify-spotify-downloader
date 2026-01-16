# Homebrew Cask for Sunnify
# Install: brew install --cask sunnypatell/tap/sunnify

cask "sunnify" do
  version "2.0.1"
  sha256 :no_check  # Updated on release

  url "https://github.com/sunnypatell/sunnify-spotify-downloader/releases/download/v#{version}/Sunnify-macOS.zip"
  name "Sunnify"
  desc "Download Spotify playlists to local MP3s with artwork and tags"
  homepage "https://github.com/sunnypatell/sunnify-spotify-downloader"

  # FFmpeg is required for audio conversion
  depends_on formula: "ffmpeg"

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
    FFmpeg will be installed automatically as a dependency.
    Educational use only. Ensure compliance with copyright laws.
  EOS
end
