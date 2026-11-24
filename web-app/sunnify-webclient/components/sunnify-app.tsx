"use client"

import React, { useState } from "react"
import {
  Music2,
  Download,
  Loader2,
  Globe,
  Apple,
  Monitor,
  Terminal,
  Disc3,
  Sparkles,
  ExternalLink,
  Clock,
  X,
  Heart,
  Coffee,
} from "lucide-react"
// lucide 1.x dropped brand marks; these come from Font Awesome via react-icons
import { FaGithub, FaLinkedin } from "react-icons/fa6"
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

const API_BASE = "https://sunnify-spotify-downloader.onrender.com"

function textOr(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback
}

// the response is data from a network we don't control: keep only the fields we
// render, as strings, and only https images (the page's CSP allows nothing else)
function toTracks(raw: unknown): Track[] {
  if (!Array.isArray(raw)) return []
  return raw
    .filter((t): t is Record<string, unknown> => typeof t === "object" && t !== null)
    .map((t) => {
      const cover = textOr(t.cover)
      return {
        id: textOr(t.id),
        title: textOr(t.title, "Unknown"),
        artists: textOr(t.artists),
        album: textOr(t.album),
        cover: cover.startsWith("https://") ? cover : "",
        releaseDate: textOr(t.releaseDate),
        downloadLink: "",
      }
    })
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
  const [showBanner, setShowBanner] = useState(true)

  const handleProcess = async () => {
    if (!playlistLink) {
      toast.error("Please enter a Spotify URL")
      return
    }

    // validate by hostname, not substring: "evil.com/open.spotify.com" must not pass
    let host = ""
    try {
      host = new URL(playlistLink).hostname
    } catch {
      host = ""
    }
    if (host !== "open.spotify.com") {
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

    // the free backend can take ~50s to wake; past 90s something else is wrong
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), 90_000)
    try {
      const response = await fetch(`${API_BASE}/api/scrape-playlist`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ playlistUrl: playlistLink }),
        signal: controller.signal,
      })

      const result = await response.json().catch(() => null)
      if (!response.ok || !result) {
        if (response.status === 429) throw new Error("Too many requests - try again in a minute")
        throw new Error(result?.data?.message || "Failed to process playlist")
      }

      if (result.event === "complete") {
        setPlaylistName(textOr(result.data?.playlistName, "Playlist"))
        const processedTracks = toTracks(result.data?.tracks)
        setTracks(processedTracks)
        setTotalSongs(processedTracks.length)
        setSongsDownloaded(processedTracks.length)
        setDownloadProgress(100)
        setStatusMessage(
          result.data?.truncated
            ? `Showing the first ${processedTracks.length} tracks`
            : `Found ${processedTracks.length} tracks`
        )

        if (processedTracks.length > 0) {
          setSelectedTrack(processedTracks[0])
        }

        toast.success(`Loaded ${processedTracks.length} tracks!`)
      } else if (result.event === "error") {
        throw new Error(result.data?.message || "Processing failed")
      }
    } catch (error) {
      console.error("Error:", error)
      const aborted = error instanceof DOMException && error.name === "AbortError"
      toast.error(
        aborted
          ? "The server took too long - try again"
          : error instanceof Error
            ? error.message
            : "Failed to process"
      )
      setStatusMessage("Error - try again")
    } finally {
      clearTimeout(timer)
      setIsProcessing(false)
    }
  }

  return (
    <div className="relative min-h-screen overflow-hidden bg-black text-white">
      {/* Animated background */}
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -top-1/4 -left-1/4 h-[800px] w-[800px] rounded-full bg-green-500/10 blur-[120px]" />
        <div className="absolute -right-1/4 -bottom-1/4 h-[600px] w-[600px] rounded-full bg-emerald-500/10 blur-[100px]" />
        <div className="absolute top-1/2 left-1/2 h-[400px] w-[400px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-green-600/5 blur-[80px]" />
      </div>

      <Toaster
        position="top-center"
        toastOptions={{
          style: { background: "#1a1a1a", color: "#fff", border: "1px solid #333" },
        }}
      />

      {/* Cold Start Banner */}
      {showBanner && (
        <div className="relative z-50 border-b border-amber-500/20 bg-amber-500/10 px-4 py-3 backdrop-blur-xs">
          <div className="mx-auto flex max-w-7xl items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <Clock className="h-4 w-4 shrink-0 text-amber-400" />
              <p className="text-sm text-amber-200">
                <span className="font-semibold">Heads up:</span> The backend runs on a free server
                that spins down after inactivity. First request may take up to 50 seconds to wake
                up.
              </p>
            </div>
            <button
              onClick={() => setShowBanner(false)}
              className="shrink-0 rounded-lg p-1 text-amber-400 transition-colors hover:bg-amber-500/20"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {/* Info Banner - Web Preview Only */}
      <div className="relative z-40 border-b border-blue-500/20 bg-blue-500/10 px-4 py-3 backdrop-blur-xs">
        <div className="mx-auto flex max-w-7xl items-center justify-center gap-3">
          <Download className="h-4 w-4 shrink-0 text-blue-400" />
          <p className="text-sm text-blue-200">
            <span className="font-semibold">Preview mode:</span> This web app displays playlist
            metadata only. To download MP3s, use the{" "}
            <a
              href="https://github.com/sunnypatell/sunnify-spotify-downloader/releases/latest"
              className="font-semibold underline hover:text-blue-100"
            >
              desktop app
            </a>
            .
          </p>
        </div>
      </div>

      <div className="relative mx-auto flex min-h-screen max-w-7xl flex-col px-4 py-8 sm:px-6 lg:px-8">
        {/* Header */}
        <header className="mb-12 text-center">
          <div className="mb-4 inline-flex items-center gap-4">
            <div className="relative">
              <div className="absolute inset-0 animate-pulse rounded-2xl bg-green-500/20 blur-xl" />
              <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl bg-linear-to-br from-green-400 via-green-500 to-emerald-600 shadow-2xl shadow-green-500/25">
                <Disc3 className="h-9 w-9 text-white" />
              </div>
            </div>
            <div className="text-left">
              <h1 className="bg-linear-to-r from-green-400 via-emerald-400 to-green-500 bg-clip-text text-5xl font-black tracking-tight text-transparent">
                Sunnify
              </h1>
              <p className="text-sm font-medium text-gray-400">Spotify Playlist Downloader</p>
            </div>
          </div>
        </header>

        {/* Main Content */}
        <div className="grid flex-1 gap-8 lg:grid-cols-[1fr_380px]">
          {/* Left Column */}
          <div className="space-y-6">
            {/* Search Card */}
            <div className="group relative overflow-hidden rounded-3xl border border-white/10 bg-white/5 p-8 backdrop-blur-xl transition-all hover:border-green-500/30 hover:bg-white/[0.07]">
              <div className="absolute -top-20 -right-20 h-40 w-40 rounded-full bg-green-500/10 blur-3xl transition-all group-hover:bg-green-500/20" />

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
                      className="h-14 rounded-xl border-white/10 bg-black/50 pr-5 pl-5 text-base text-white placeholder:text-gray-500 focus:border-green-500 focus:ring-2 focus:ring-green-500/20"
                    />
                  </div>
                  <Button
                    onClick={handleProcess}
                    disabled={isProcessing}
                    className="h-14 rounded-xl bg-linear-to-r from-green-500 to-emerald-500 px-8 text-base font-bold text-black shadow-lg shadow-green-500/25 transition-all hover:scale-105 hover:shadow-green-500/40 disabled:scale-100 disabled:opacity-50"
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
                    className="h-2 rounded-full bg-white/10 [&>div]:rounded-full [&>div]:bg-linear-to-r [&>div]:from-green-400 [&>div]:to-emerald-500"
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
                        <div className="flex h-full w-full items-center justify-center bg-linear-to-br from-gray-800 to-gray-900">
                          <Music2 className="h-20 w-20 text-gray-700" />
                        </div>
                      )}
                      <div className="absolute inset-0 bg-linear-to-t from-black/60 via-transparent to-transparent" />
                    </div>

                    <div className="space-y-4">
                      <div>
                        <p className="mb-1 text-xs font-semibold tracking-widest text-green-400 uppercase">
                          Title
                        </p>
                        <p className="text-lg leading-tight font-bold">{selectedTrack.title}</p>
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <p className="mb-1 text-xs font-semibold tracking-widest text-gray-500 uppercase">
                            Artist
                          </p>
                          <p className="text-sm text-gray-300">{selectedTrack.artists}</p>
                        </div>
                        <div>
                          <p className="mb-1 text-xs font-semibold tracking-widest text-gray-500 uppercase">
                            Album
                          </p>
                          <p className="text-sm text-gray-300">{selectedTrack.album || "—"}</p>
                        </div>
                        <div className="col-span-2">
                          <p className="mb-1 text-xs font-semibold tracking-widest text-gray-500 uppercase">
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
                <code className="block text-xs text-green-400">
                  brew tap sunnypatell/sunnify
                  https://github.com/sunnypatell/sunnify-spotify-downloader
                </code>
                <code className="block text-xs text-green-400">
                  brew install --cask sunnypatell/sunnify/sunnify
                </code>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <footer className="mt-12 border-t border-white/10 pt-8">
          <div className="flex flex-col items-center justify-between gap-6 sm:flex-row">
            <p className="text-sm text-gray-500">
              © 2026 Sunny Jayendra Patel — Educational use only
            </p>

            {/* Sponsor Buttons */}
            <div className="flex items-center gap-3">
              <a
                href="https://buymeacoffee.com/sunnypatell"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 rounded-xl bg-amber-500/10 px-4 py-2 text-sm font-medium text-amber-400 transition-all hover:bg-amber-500/20 hover:text-amber-300"
              >
                <Coffee className="h-4 w-4" />
                Buy Me a Coffee
              </a>
              <a
                href="https://github.com/sponsors/sunnypatell"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 rounded-xl bg-pink-500/10 px-4 py-2 text-sm font-medium text-pink-400 transition-all hover:bg-pink-500/20 hover:text-pink-300"
              >
                <Heart className="h-4 w-4" />
                Sponsor
              </a>
            </div>

            {/* Social Links */}
            <div className="flex items-center gap-2">
              <a
                href="https://github.com/sunnypatell/sunnify-spotify-downloader"
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-xl p-3 text-gray-500 transition-all hover:bg-white/5 hover:text-white"
              >
                <FaGithub className="h-5 w-5" />
              </a>
              <a
                href="https://www.linkedin.com/in/sunny-patel-30b460204/"
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-xl p-3 text-gray-500 transition-all hover:bg-white/5 hover:text-white"
              >
                <FaLinkedin className="h-5 w-5" />
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
          </div>
        </footer>
      </div>
    </div>
  )
}
