import type { Metadata } from "next"
import localFont from "next/font/local"
import "./globals.css"

const geistSans = localFont({
  src: "./fonts/GeistVF.woff",
  variable: "--font-geist-sans",
  weight: "100 900",
})
const geistMono = localFont({
  src: "./fonts/GeistMonoVF.woff",
  variable: "--font-geist-mono",
  weight: "100 900",
})

export const metadata: Metadata = {
  title: "Sunnify - Spotify Playlist Downloader",
  description:
    "Download entire Spotify playlists to local MP3s with embedded artwork and tags. Free, open-source, no account required.",
  keywords: ["spotify", "downloader", "mp3", "playlist", "music", "converter"],
  authors: [{ name: "Sunny Jayendra Patel" }],
  openGraph: {
    title: "Sunnify - Spotify Playlist Downloader",
    description: "Download Spotify playlists to MP3 with artwork and tags",
    type: "website",
  },
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>{children}</body>
    </html>
  )
}
