import type { Metadata } from "next"
import localFont from "next/font/local"
import { Analytics } from "@vercel/analytics/next"
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
  metadataBase: new URL("https://sunnify-spotify-downloader.vercel.app"),
  title: "Sunnify - Spotify Playlist Downloader",
  description:
    "Download entire Spotify playlists to local MP3s with embedded artwork and tags. Free, open-source, no account required.",
  applicationName: "Sunnify",
  keywords: ["spotify", "downloader", "mp3", "playlist", "music", "converter"],
  authors: [{ name: "Sunny Jayendra Patel", url: "https://github.com/sunnypatell" }],
  creator: "Sunny Jayendra Patel",
  publisher: "Sunny Jayendra Patel",
  alternates: { canonical: "/" },
  icons: { icon: "/icon.png", apple: "/icon.png" },
  openGraph: {
    title: "Sunnify - Spotify Playlist Downloader",
    description: "Download Spotify playlists to MP3 with artwork and tags",
    url: "/",
    siteName: "Sunnify",
    type: "website",
  },
  twitter: {
    card: "summary",
    title: "Sunnify - Spotify Playlist Downloader",
    description: "Download Spotify playlists to MP3 with artwork and tags",
  },
  robots: { index: true, follow: true },
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        {children}
        <Analytics />
      </body>
    </html>
  )
}
