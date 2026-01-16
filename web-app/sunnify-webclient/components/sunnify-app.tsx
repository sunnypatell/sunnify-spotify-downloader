"use client"

import React, { useState } from "react"
import {
  Music2,
  Download,
  Loader2,
  Github,
  Linkedin,
  Globe,
  Apple,
  Monitor,
  Terminal,
  Disc3,
  Sparkles,
  ExternalLink,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Progress } from "@/components/ui/progress"
import { ScrollArea } from "@/components/ui/scroll-area"
import { toast, Toaster } from "react-hot-toast"
import Image from "next/image"

interface Track {
  id: string
  title: string
  artists: string
  album: string
  cover: string
  releaseDate: string
  downloadLink: string
}

export default function SunnifyApp() {
  const [playlistLink, setPlaylistLink] = useState("")
  const [downloadProgress, setDownloadProgress] = useState(0)
  const [songsDownloaded, setSongsDownloaded] = useState(0)
  const [totalSongs, setTotalSongs] = useState(0)
  const [playlistName, setPlaylistName] = useState("")
  const [isProcessing, setIsProcessing] = useState(false)
  const [statusMessage, setStatusMessage] = useState("Paste a Spotify URL to begin")
  const [tracks, setTracks] = useState<Track[]>([])
  const [selectedTrack, setSelectedTrack] = useState<Track | null>(null)

  const handleProcess = async () => {
    if (!playlistLink) {
      toast.error("Please enter a Spotify URL")
      return
    }

    if (!playlistLink.includes("open.spotify.com")) {
      toast.error("Invalid URL - must be from open.spotify.com")
      return
    }

    setIsProcessing(true)
    setDownloadProgress(0)
    setSongsDownloaded(0)
    setTotalSongs(0)
    setStatusMessage("Fetching playlist data...")
    setTracks([])
    setSelectedTrack(null)

    try {
      const response = await fetch(
        "https://coxpynrvnl46ro5bybq7aikbim0vmypk.lambda-url.us-east-2.on.aws/api/scrape-playlist",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ playlistUrl: playlistLink }),
        }
      )

      if (!response.ok) throw new Error("Failed to process playlist")

      const result = await response.json()

      if (result.event === "complete") {
        setPlaylistName(result.data.playlistName || "Playlist")
        const processedTracks: Track[] = result.data.tracks || []
        setTracks(processedTracks)
        setTotalSongs(processedTracks.length)
        setSongsDownloaded(processedTracks.length)
        setDownloadProgress(100)
        setStatusMessage(`Found ${processedTracks.length} tracks`)

        if (processedTracks.length > 0) {
          setSelectedTrack(processedTracks[0])
        }

        toast.success(`Loaded ${processedTracks.length} tracks!`)
      } else if (result.event === "error") {
        throw new Error(result.data?.message || "Processing failed")
      }
    } catch (error) {
      console.error("Error:", error)
      toast.error(error instanceof Error ? error.message : "Failed to process")
      setStatusMessage("Error - try again")
    } finally {
      setIsProcessing(false)
    }
  }

  return (
    <div className="relative min-h-screen overflow-hidden bg-black text-white">
      {/* Animated background */}
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -left-1/4 -top-1/4 h-[800px] w-[800px] rounded-full bg-green-500/10 blur-[120px]" />
        <div className="absolute -bottom-1/4 -right-1/4 h-[600px] w-[600px] rounded-full bg-emerald-500/10 blur-[100px]" />
        <div className="absolute left-1/2 top-1/2 h-[400px] w-[400px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-green-600/5 blur-[80px]" />
      </div>

      <Toaster
        position="top-center"
        toastOptions={{
          style: { background: "#1a1a1a", color: "#fff", border: "1px solid #333" },
        }}
      />

      <div className="relative mx-auto flex min-h-screen max-w-7xl flex-col px-4 py-8 sm:px-6 lg:px-8">
        {/* Header */}
        <header className="mb-12 text-center">
          <div className="mb-4 inline-flex items-center gap-4">
            <div className="relative">
              <div className="absolute inset-0 animate-pulse rounded-2xl bg-green-500/20 blur-xl" />
              <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-green-400 via-green-500 to-emerald-600 shadow-2xl shadow-green-500/25">
                <Disc3 className="h-9 w-9 text-white" />
              </div>
            </div>
            <div className="text-left">
              <h1 className="bg-gradient-to-r from-green-400 via-emerald-400 to-green-500 bg-clip-text text-5xl font-black tracking-tight text-transparent">
                Sunnify
              </h1>
              <p className="text-sm font-medium text-gray-400">Spotify Playlist Downloader</p>
            </div>
          </div>
        </header>

        {/* Main Content */}
        <div className="grid flex-1 gap-8 lg:grid-cols-[1fr,380px]">
          {/* Left Column */}
          <div className="space-y-6">
            {/* Search Card */}
            <div className="group relative overflow-hidden rounded-3xl border border-white/10 bg-white/5 p-8 backdrop-blur-xl transition-all hover:border-green-500/30 hover:bg-white/[0.07]">
              <div className="absolute -right-20 -top-20 h-40 w-40 rounded-full bg-green-500/10 blur-3xl transition-all group-hover:bg-green-500/20" />

              <div className="relative">
                <div className="mb-6 flex items-center gap-3">
                  <Sparkles className="h-5 w-5 text-green-400" />
                  <h2 className="text-xl font-bold">Enter Spotify URL</h2>
                </div>

                <div className="flex gap-4">
                  <div className="relative flex-1">
                    <Input
                      type="text"
                      placeholder="https://open.spotify.com/playlist/..."
                      value={playlistLink}
                      onChange={(e) => setPlaylistLink(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && !isProcessing && handleProcess()}
                      className="h-14 rounded-xl border-white/10 bg-black/50 pl-5 pr-5 text-base text-white placeholder:text-gray-500 focus:border-green-500 focus:ring-2 focus:ring-green-500/20"
                    />
                  </div>
                  <Button
                    onClick={handleProcess}
                    disabled={isProcessing}
                    className="h-14 rounded-xl bg-gradient-to-r from-green-500 to-emerald-500 px-8 text-base font-bold text-black shadow-lg shadow-green-500/25 transition-all hover:scale-105 hover:shadow-green-500/40 disabled:scale-100 disabled:opacity-50"
                  >
                    {isProcessing ? (
                      <Loader2 className="h-6 w-6 animate-spin" />
                    ) : (
                      <>
                        <Download className="mr-2 h-5 w-5" />
                        Fetch
                      </>
                    )}
                  </Button>
                </div>

                {/* Progress */}
                <div className="mt-6 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-400">{statusMessage}</span>
                    {totalSongs > 0 && (
                      <span className="rounded-full bg-green-500/10 px-3 py-1 text-sm font-semibold text-green-400">
                        {songsDownloaded} / {totalSongs}
                      </span>
                    )}
                  </div>
                  <Progress
                    value={downloadProgress}
                    className="h-2 rounded-full bg-white/10 [&>div]:rounded-full [&>div]:bg-gradient-to-r [&>div]:from-green-400 [&>div]:to-emerald-500"
                  />
                  {playlistName && (
                    <p className="text-sm">
                      <span className="text-gray-500">Playlist:</span>{" "}
                      <span className="font-medium text-white">{playlistName}</span>
                    </p>
                  )}
                </div>
              </div>
            </div>

            {/* Track List */}
            <div className="overflow-hidden rounded-3xl border border-white/10 bg-white/5 backdrop-blur-xl">
              <div className="border-b border-white/10 px-8 py-5">
                <h2 className="text-xl font-bold">
                  {tracks.length > 0 ? `${tracks.length} Tracks` : "Track List"}
                </h2>
              </div>

              {tracks.length === 0 ? (
                <div className="flex h-80 flex-col items-center justify-center px-8 text-center">
                  <div className="mb-4 rounded-full bg-white/5 p-6">
                    <Music2 className="h-10 w-10 text-gray-600" />
                  </div>
                  <p className="text-lg font-medium text-gray-400">No tracks yet</p>
                  <p className="mt-1 text-sm text-gray-600">
                    Enter a Spotify playlist or track URL above
                  </p>
                </div>
              ) : (
                <ScrollArea className="h-[420px]">
                  <div className="divide-y divide-white/5">
                    {tracks.map((track, index) => (
                      <div
                        key={track.id || index}
                        onClick={() => setSelectedTrack(track)}
                        className={`flex cursor-pointer items-center gap-4 px-6 py-4 transition-all hover:bg-white/5 ${
                          selectedTrack?.id === track.id ? "bg-green-500/10" : ""
                        }`}
                      >
                        <span className="w-8 text-center text-sm font-medium text-gray-500">
                          {index + 1}
                        </span>
                        {track.cover ? (
                          <Image
                            src={track.cover}
                            alt=""
                            width={56}
                            height={56}
                            className="h-14 w-14 rounded-lg object-cover shadow-lg"
                            unoptimized
                          />
                        ) : (
                          <div className="flex h-14 w-14 items-center justify-center rounded-lg bg-white/10">
                            <Music2 className="h-6 w-6 text-gray-500" />
                          </div>
                        )}
                        <div className="min-w-0 flex-1">
                          <p className="truncate font-semibold">{track.title}</p>
                          <p className="truncate text-sm text-gray-400">{track.artists}</p>
                        </div>
                        {selectedTrack?.id === track.id && (
                          <div className="h-2 w-2 rounded-full bg-green-500" />
                        )}
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              )}
            </div>
          </div>

          {/* Right Column */}
          <div className="space-y-6">
            {/* Now Playing */}
            <div className="overflow-hidden rounded-3xl border border-white/10 bg-white/5 backdrop-blur-xl">
              <div className="border-b border-white/10 px-6 py-4">
                <h2 className="font-bold">Now Playing</h2>
              </div>

              <div className="p-6">
                {selectedTrack ? (
                  <div className="space-y-6">
                    <div className="relative mx-auto aspect-square w-full max-w-[280px] overflow-hidden rounded-2xl shadow-2xl shadow-black/50">
                      {selectedTrack.cover ? (
                        <Image
                          src={selectedTrack.cover}
                          alt={selectedTrack.title}
                          fill
                          className="object-cover"
                          unoptimized
                        />
                      ) : (
                        <div className="flex h-full w-full items-center justify-center bg-gradient-to-br from-gray-800 to-gray-900">
                          <Music2 className="h-20 w-20 text-gray-700" />
                        </div>
                      )}
                      <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent" />
                    </div>

                    <div className="space-y-4">
                      <div>
                        <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-green-400">
                          Title
                        </p>
                        <p className="text-lg font-bold leading-tight">{selectedTrack.title}</p>
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-gray-500">
                            Artist
                          </p>
                          <p className="text-sm text-gray-300">{selectedTrack.artists}</p>
                        </div>
                        <div>
                          <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-gray-500">
                            Album
                          </p>
                          <p className="text-sm text-gray-300">{selectedTrack.album || "—"}</p>
                        </div>
                        <div className="col-span-2">
                          <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-gray-500">
                            Release Date
                          </p>
                          <p className="text-sm text-gray-300">
                            {selectedTrack.releaseDate || "—"}
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="flex aspect-square flex-col items-center justify-center rounded-2xl bg-black/30 text-center">
                    <Disc3 className="mb-3 h-16 w-16 text-gray-700" />
                    <p className="font-medium text-gray-500">Select a track</p>
                  </div>
                )}
              </div>
            </div>

            {/* Download Desktop */}
            <div className="overflow-hidden rounded-3xl border border-white/10 bg-white/5 p-6 backdrop-blur-xl">
              <div className="mb-4 flex items-center gap-2">
                <Download className="h-5 w-5 text-green-400" />
                <h2 className="font-bold">Desktop App</h2>
              </div>
              <p className="mb-5 text-sm text-gray-400">
                Full offline experience with bundled FFmpeg.
              </p>

              <div className="space-y-2">
                <a
                  href="https://github.com/sunnypatell/sunnify-spotify-downloader/releases/latest"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-between rounded-xl bg-black/40 px-4 py-3 transition-all hover:bg-white/10"
                >
                  <div className="flex items-center gap-3">
                    <Monitor className="h-5 w-5 text-blue-400" />
                    <span className="font-medium">Windows</span>
                  </div>
                  <ExternalLink className="h-4 w-4 text-gray-500" />
                </a>
                <a
                  href="https://github.com/sunnypatell/sunnify-spotify-downloader/releases/latest"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-between rounded-xl bg-black/40 px-4 py-3 transition-all hover:bg-white/10"
                >
                  <div className="flex items-center gap-3">
                    <Apple className="h-5 w-5 text-gray-300" />
                    <span className="font-medium">macOS</span>
                  </div>
                  <ExternalLink className="h-4 w-4 text-gray-500" />
                </a>
                <a
                  href="https://github.com/sunnypatell/sunnify-spotify-downloader/releases/latest"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-between rounded-xl bg-black/40 px-4 py-3 transition-all hover:bg-white/10"
                >
                  <div className="flex items-center gap-3">
                    <Terminal className="h-5 w-5 text-orange-400" />
                    <span className="font-medium">Linux</span>
                  </div>
                  <ExternalLink className="h-4 w-4 text-gray-500" />
                </a>
              </div>

              <div className="mt-4 rounded-xl bg-black/40 p-3">
                <p className="mb-1 text-xs font-semibold text-gray-500">Homebrew (macOS)</p>
                <code className="text-xs text-green-400">
                  brew install --cask sunnypatell/tap/sunnify
                </code>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <footer className="mt-12 flex flex-col items-center justify-between gap-6 border-t border-white/10 pt-8 sm:flex-row">
          <p className="text-sm text-gray-500">
            © 2026 Sunny Jayendra Patel — Educational use only
          </p>
          <div className="flex items-center gap-2">
            <a
              href="https://github.com/sunnypatell/sunnify-spotify-downloader"
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-xl p-3 text-gray-500 transition-all hover:bg-white/5 hover:text-white"
            >
              <Github className="h-5 w-5" />
            </a>
            <a
              href="https://www.linkedin.com/in/sunny-patel-30b460204/"
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-xl p-3 text-gray-500 transition-all hover:bg-white/5 hover:text-white"
            >
              <Linkedin className="h-5 w-5" />
            </a>
            <a
              href="https://www.sunnypatel.net/"
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-xl p-3 text-gray-500 transition-all hover:bg-white/5 hover:text-white"
            >
              <Globe className="h-5 w-5" />
            </a>
          </div>
        </footer>
      </div>
    </div>
  )
}
