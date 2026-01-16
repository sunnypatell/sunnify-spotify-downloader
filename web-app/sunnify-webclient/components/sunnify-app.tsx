"use client"

import React, { useState } from "react"
import { Music2, Download, Loader2, Github, Linkedin, Globe, Apple, Monitor } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Progress } from "@/components/ui/progress"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Switch } from "@/components/ui/switch"
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
  const [currentTrack, setCurrentTrack] = useState<Track | null>(null)
  const [downloadProgress, setDownloadProgress] = useState(0)
  const [songsDownloaded, setSongsDownloaded] = useState(0)
  const [totalSongs, setTotalSongs] = useState(0)
  const [playlistName, setPlaylistName] = useState("")
  const [isProcessing, setIsProcessing] = useState(false)
  const [statusMessage, setStatusMessage] = useState("Ready")
  const [tracks, setTracks] = useState<Track[]>([])
  const [showPreview, setShowPreview] = useState(true)
  const [selectedTrack, setSelectedTrack] = useState<Track | null>(null)

  const handleProcess = async () => {
    if (!playlistLink) {
      toast.error("Please enter a Spotify URL")
      return
    }

    if (!playlistLink.includes("open.spotify.com")) {
      toast.error("Please enter a valid Spotify URL")
      return
    }

    setIsProcessing(true)
    setDownloadProgress(0)
    setSongsDownloaded(0)
    setTotalSongs(0)
    setStatusMessage("Connecting...")
    setTracks([])
    setCurrentTrack(null)

    try {
      const response = await fetch(
        "https://coxpynrvnl46ro5bybq7aikbim0vmypk.lambda-url.us-east-2.on.aws/api/scrape-playlist",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ playlistUrl: playlistLink }),
        }
      )

      if (!response.ok) {
        throw new Error("Failed to process playlist")
      }

      const result = await response.json()

      if (result.event === "complete") {
        setPlaylistName(result.data.playlistName || "Playlist")
        const processedTracks: Track[] = result.data.tracks || []
        setTracks(processedTracks)
        setTotalSongs(processedTracks.length)
        setSongsDownloaded(processedTracks.length)
        setDownloadProgress(100)
        setStatusMessage("Processing complete!")

        if (processedTracks.length > 0) {
          setCurrentTrack(processedTracks[0])
          setSelectedTrack(processedTracks[0])
        }

        toast.success(`Found ${processedTracks.length} tracks!`)
      } else if (result.event === "error") {
        throw new Error(result.data?.message || "Processing failed")
      }
    } catch (error) {
      console.error("Error:", error)
      toast.error(error instanceof Error ? error.message : "Failed to process playlist")
      setStatusMessage("Error occurred")
    } finally {
      setIsProcessing(false)
    }
  }

  const handleTrackClick = (track: Track) => {
    setSelectedTrack(track)
    setCurrentTrack(track)
  }

  return (
    <div className="min-h-screen bg-[#1a1a2e] text-white">
      <Toaster position="top-center" />

      {/* Main Container */}
      <div className="mx-auto flex min-h-screen max-w-6xl flex-col p-6">
        {/* Header */}
        <header className="mb-8 text-center">
          <div className="mb-2 flex items-center justify-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-green-400 to-green-600 shadow-lg shadow-green-500/20">
              <Music2 className="h-7 w-7 text-white" />
            </div>
            <h1 className="text-4xl font-bold tracking-tight">
              <span className="text-green-400">Sunnify</span>
            </h1>
          </div>
          <p className="text-sm text-gray-400">Spotify Playlist Downloader</p>
        </header>

        {/* Main Content Grid */}
        <div className="grid flex-1 gap-6 lg:grid-cols-[1fr,320px]">
          {/* Left Panel - Controls & Track List */}
          <div className="flex flex-col gap-6">
            {/* Input Card */}
            <div className="rounded-2xl bg-[#16213e] p-6 shadow-xl">
              <label className="mb-2 block text-sm font-medium text-gray-300">
                Spotify Playlist or Track URL
              </label>
              <div className="flex gap-3">
                <Input
                  type="text"
                  placeholder="https://open.spotify.com/playlist/..."
                  value={playlistLink}
                  onChange={(e) => setPlaylistLink(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleProcess()}
                  className="flex-1 border-gray-700 bg-[#0f0f1a] text-white placeholder:text-gray-500 focus:border-green-500 focus:ring-green-500/20"
                />
                <Button
                  onClick={handleProcess}
                  disabled={isProcessing}
                  className="bg-green-500 px-8 font-semibold text-black hover:bg-green-400 disabled:opacity-50"
                >
                  {isProcessing ? (
                    <Loader2 className="h-5 w-5 animate-spin" />
                  ) : (
                    <Download className="h-5 w-5" />
                  )}
                </Button>
              </div>

              {/* Progress Section */}
              <div className="mt-5">
                <div className="mb-2 flex items-center justify-between text-sm">
                  <span className="text-gray-400">{statusMessage}</span>
                  <span className="font-mono text-green-400">
                    {songsDownloaded}/{totalSongs || "0"}
                  </span>
                </div>
                <Progress
                  value={downloadProgress}
                  className="h-2 bg-gray-800 [&>div]:bg-gradient-to-r [&>div]:from-green-500 [&>div]:to-green-400"
                />
                {playlistName && (
                  <p className="mt-2 text-sm text-gray-400">
                    Playlist: <span className="text-white">{playlistName}</span>
                  </p>
                )}
              </div>
            </div>

            {/* Track List */}
            <div className="flex-1 rounded-2xl bg-[#16213e] p-6 shadow-xl">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="text-lg font-semibold">Tracks</h2>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-400">Show Preview</span>
                  <Switch
                    checked={showPreview}
                    onCheckedChange={setShowPreview}
                    className="data-[state=checked]:bg-green-500"
                  />
                </div>
              </div>

              {tracks.length === 0 ? (
                <div className="flex h-64 flex-col items-center justify-center text-gray-500">
                  <Music2 className="mb-3 h-12 w-12 opacity-30" />
                  <p>Enter a Spotify URL to get started</p>
                </div>
              ) : (
                <ScrollArea className="h-[400px] pr-4">
                  <div className="space-y-2">
                    {tracks.map((track, index) => (
                      <div
                        key={track.id || index}
                        onClick={() => handleTrackClick(track)}
                        className={`flex cursor-pointer items-center gap-3 rounded-lg p-3 transition-all hover:bg-white/5 ${
                          selectedTrack?.id === track.id
                            ? "bg-green-500/10 ring-1 ring-green-500/30"
                            : ""
                        }`}
                      >
                        {track.cover && (
                          <Image
                            src={track.cover}
                            alt={track.title}
                            width={48}
                            height={48}
                            className="h-12 w-12 rounded-md object-cover"
                            unoptimized
                          />
                        )}
                        <div className="min-w-0 flex-1">
                          <p className="truncate font-medium">{track.title}</p>
                          <p className="truncate text-sm text-gray-400">{track.artists}</p>
                        </div>
                        <span className="text-xs text-gray-500">{index + 1}</span>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              )}
            </div>
          </div>

          {/* Right Panel - Preview & Downloads */}
          <div className="flex flex-col gap-6">
            {/* Preview Card */}
            {showPreview && (
              <div className="rounded-2xl bg-[#16213e] p-6 shadow-xl">
                <h2 className="mb-4 text-lg font-semibold">Now Playing</h2>

                {selectedTrack ? (
                  <div className="text-center">
                    <div className="relative mx-auto mb-4 aspect-square w-full max-w-[200px] overflow-hidden rounded-xl shadow-lg shadow-black/50">
                      {selectedTrack.cover ? (
                        <Image
                          src={selectedTrack.cover}
                          alt={selectedTrack.title}
                          fill
                          className="object-cover"
                          unoptimized
                        />
                      ) : (
                        <div className="flex h-full w-full items-center justify-center bg-gray-800">
                          <Music2 className="h-16 w-16 text-gray-600" />
                        </div>
                      )}
                    </div>

                    <div className="space-y-3 text-left">
                      <div>
                        <p className="text-xs uppercase tracking-wider text-gray-500">Title</p>
                        <p className="font-medium">{selectedTrack.title}</p>
                      </div>
                      <div>
                        <p className="text-xs uppercase tracking-wider text-gray-500">Artist</p>
                        <p className="text-gray-300">{selectedTrack.artists}</p>
                      </div>
                      <div>
                        <p className="text-xs uppercase tracking-wider text-gray-500">Album</p>
                        <p className="text-gray-300">{selectedTrack.album || "—"}</p>
                      </div>
                      <div>
                        <p className="text-xs uppercase tracking-wider text-gray-500">
                          Release Date
                        </p>
                        <p className="text-gray-300">{selectedTrack.releaseDate || "—"}</p>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="flex aspect-square flex-col items-center justify-center rounded-xl bg-[#0f0f1a] text-gray-500">
                    <Music2 className="mb-2 h-12 w-12 opacity-30" />
                    <p className="text-sm">Select a track</p>
                  </div>
                )}
              </div>
            )}

            {/* Download Apps Card */}
            <div className="rounded-2xl bg-[#16213e] p-6 shadow-xl">
              <h2 className="mb-4 text-lg font-semibold">Download Desktop App</h2>
              <p className="mb-4 text-sm text-gray-400">
                Get the full experience with bundled FFmpeg and offline support.
              </p>
              <div className="space-y-2">
                <a
                  href="https://github.com/sunnypatell/sunnify-spotify-downloader/releases/latest"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-3 rounded-lg bg-[#0f0f1a] p-3 transition-colors hover:bg-white/5"
                >
                  <Monitor className="h-5 w-5 text-blue-400" />
                  <span>Windows</span>
                </a>
                <a
                  href="https://github.com/sunnypatell/sunnify-spotify-downloader/releases/latest"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-3 rounded-lg bg-[#0f0f1a] p-3 transition-colors hover:bg-white/5"
                >
                  <Apple className="h-5 w-5 text-gray-300" />
                  <span>macOS</span>
                </a>
              </div>
              <p className="mt-3 text-xs text-gray-500">
                macOS:{" "}
                <code className="rounded bg-black/30 px-1">
                  brew install --cask sunnypatell/sunnify/sunnify
                </code>
              </p>
            </div>
          </div>
        </div>

        {/* Footer */}
        <footer className="mt-8 border-t border-gray-800 pt-6">
          <div className="flex flex-col items-center justify-between gap-4 sm:flex-row">
            <p className="text-sm text-gray-500">
              © 2026 Sunny Jayendra Patel. Educational use only.
            </p>
            <div className="flex items-center gap-3">
              <a
                href="https://github.com/sunnypatell/sunnify-spotify-downloader"
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-lg p-2 text-gray-400 transition-colors hover:bg-white/5 hover:text-white"
              >
                <Github className="h-5 w-5" />
              </a>
              <a
                href="https://www.linkedin.com/in/sunny-patel-30b460204/"
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-lg p-2 text-gray-400 transition-colors hover:bg-white/5 hover:text-white"
              >
                <Linkedin className="h-5 w-5" />
              </a>
              <a
                href="https://www.sunnypatel.net/"
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-lg p-2 text-gray-400 transition-colors hover:bg-white/5 hover:text-white"
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
