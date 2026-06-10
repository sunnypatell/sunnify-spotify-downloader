import type { MetadataRoute } from "next"

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Sunnify - Spotify Playlist Downloader",
    short_name: "Sunnify",
    description:
      "Fetch Spotify playlist and track metadata in the browser. Companion to the desktop downloader.",
    start_url: "/",
    display: "standalone",
    background_color: "#0a0a0a",
    theme_color: "#1db954",
    icons: [{ src: "/icon.png", sizes: "any", type: "image/png" }],
  }
}
