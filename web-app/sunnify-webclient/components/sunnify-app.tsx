'use client'

import React, { useState, useRef, useEffect } from 'react'
import { Sun, Music, Download, X, Linkedin, Play, Pause, Github, Globe } from 'lucide-react'
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import { Progress } from "@/components/ui/progress"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import { toast, Toaster } from 'react-hot-toast'

interface Track {
  id: string;
  title: string;
  artists: string;
  album: string;
  cover: string;
  releaseDate: string;
  downloadLink: string;
}

export default function SunnifyApp() {
  const [playlistLink, setPlaylistLink] = useState('')
  const [showPreview, setShowPreview] = useState(true)
  const [addMetadata, setAddMetadata] = useState(true)
  const [currentSong, setCurrentSong] = useState<Track>({
    id: '',
    title: '',
    artists: '',
    album: '',
    cover: '',
    releaseDate: '',
    downloadLink: ''
  })
  const [downloadProgress, setDownloadProgress] = useState(0)
  const [songsDownloaded, setSongsDownloaded] = useState(0)
  const [playlistName, setPlaylistName] = useState('')
  const [isDownloading, setIsDownloading] = useState(false)
  const [statusMessage, setStatusMessage] = useState('')
  const [downloadedTracks, setDownloadedTracks] = useState<Track[]>([])
  const [isPlaying, setIsPlaying] = useState(false)
  const audioRef = useRef<HTMLAudioElement | null>(null)

  useEffect(() => {
    audioRef.current = new Audio()
  }, [])

  const handleDownload = async () => {
    if (!playlistLink) {
      toast.error('Please enter a valid Spotify playlist URL')
      return
    }

    setIsDownloading(true)
    setDownloadProgress(0)
    setSongsDownloaded(0)
    setStatusMessage("Starting download...")
    setDownloadedTracks([])

    try {
      const response = await fetch('http://localhost:5000/scrape_playlist', { // Updated backend URL
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ playlist_link: playlistLink }), // Updated payload key
      })

      if (!response.ok) {
        throw new Error('Failed to fetch playlist data')
      }

      const data = await response.json()
      setPlaylistName(data.playlistName)

      // Mock data for the tracks
      const mockTracks = data.tracks.map((track: any, i: number) => ({
        id: i.toString(),
        title: track.title,
        artists: track.artists,
        album: track.album,
        cover: track.cover,
        releaseDate: track.releaseDate,
        downloadLink: `http://localhost:5000/download/${track.id}` // Link to backend download route
      }))

      for (let i = 0; i < mockTracks.length; i++) {
        const track = mockTracks[i] as Track
        setCurrentSong(track)
        setDownloadedTracks(prev => [...prev, track])
        setSongsDownloaded(i + 1)
        setDownloadProgress(((i + 1) / mockTracks.length) * 100)
        setStatusMessage(`Processing: ${track.title} - ${track.artists}`)

        // Simulate download process
        await new Promise(resolve => setTimeout(resolve, 500))
      }

      setStatusMessage("Processing completed!")
      toast.success("Playlist processing completed!")
    } catch (error) {
      console.error('Error:', error)
      toast.error('An error occurred while processing the playlist')
    } finally {
      setIsDownloading(false)
    }
  }

  const playPauseTrack = (track: Track) => {
    if (!audioRef.current) return

    if (isPlaying && audioRef.current.src === track.downloadLink) {
      audioRef.current.pause()
      setIsPlaying(false)
    } else {
      audioRef.current.src = track.downloadLink
      audioRef.current.play()
      setIsPlaying(true)
      setCurrentSong(track)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-600 to-blue-600 p-8 text-white">
      <Toaster />
      <div className="max-w-7xl mx-auto">
        <header className="text-center mb-12">
          <h1 className="text-5xl font-bold mb-4 flex items-center justify-center">
            <Sun className="text-yellow-400 mr-4" size={48} />
            Sunnify Spotify Downloader
          </h1>
          <p className="text-xl">Download your favorite Spotify playlists with ease</p>
        </header>

        <div className="bg-white/10 backdrop-blur-lg rounded-3xl shadow-2xl overflow-hidden">
          <div className="flex flex-col md:flex-row">
            <div className="w-full md:w-1/2 p-8">
              <Input
                type="text"
                placeholder="Enter Spotify playlist URL"
                value={playlistLink}
                onChange={(e) => setPlaylistLink(e.target.value)}
                className="mb-4 bg-white/20 text-white placeholder-white/60"
              />
              <Button 
                onClick={handleDownload} 
                className="w-full mb-4 bg-green-500 hover:bg-green-600 text-white"
                disabled={isDownloading || !playlistLink}
              >
                {isDownloading ? (
                  <>
                    <Music className="mr-2 animate-spin" size={16} />
                    Processing...
                  </>
                ) : (
                  <>
                    <Download className="mr-2" size={16} />
                    Process Playlist
                  </>
                )}
              </Button>
              <div className="flex items-center justify-between mb-4">
                <label className="text-sm">Show Preview</label>
                <Switch
                  checked={showPreview}
                  onCheckedChange={setShowPreview}
                  disabled={isDownloading}
                />
              </div>
              <div className="flex items-center justify-between mb-4">
                <label className="text-sm">Add Metadata</label>
                <Switch
                  checked={addMetadata}
                  onCheckedChange={setAddMetadata}
                  disabled={isDownloading}
                />
              </div>
              <div className="mt-8">
                <h2 className="text-lg font-semibold mb-2">Processing Progress</h2>
                <Progress value={downloadProgress} className="mb-2" />
                <p className="text-sm">Songs processed: {songsDownloaded}</p>
                <p className="text-sm">Playlist: {playlistName}</p>
                <p className="text-sm mt-2">{statusMessage}</p>
              </div>
              <div className="mt-8">
                <h2 className="text-lg font-semibold mb-2">Processed Tracks</h2>
                <ScrollArea className="h-64 w-full rounded-md border border-white/20 p-4">
                  {downloadedTracks.map((track, index) => (
                    <div key={index} className="flex items-center justify-between py-2 border-b border-white/10 last:border-b-0">
                      <div>
                        <p className="font-medium">{track.title}</p>
                        <p className="text-sm opacity-70">{track.artists}</p>
                      </div>
                      <Button variant="ghost" size="icon" onClick={() => playPauseTrack(track)}>
                        {isPlaying && currentSong.id === track.id ? <Pause size={16} /> : <Play size={16} />}
                      </Button>
                    </div>
                  ))}
                </ScrollArea>
              </div>
            </div>
            <div className={`w-full md:w-1/2 bg-white/5 p-8 transition-all duration-300 ${showPreview ? 'translate-x-0' : 'translate-x-full'}`}>
              <div className="flex justify-between items-center mb-6">
                <h2 className="text-xl font-semibold">Song Preview</h2>
                <Button variant="ghost" size="icon" onClick={() => setShowPreview(false)}>
                  <X className="h-4 w-4" />
                </Button>
              </div>
              {currentSong.cover && (
                <img src={currentSong.cover} alt="Album Cover" className="w-full h-64 object-cover rounded-lg mb-4" />
              )}
              <h3 className="text-lg font-semibold mb-2">{currentSong.title}</h3>
              <p className="opacity-70 mb-1">{currentSong.artists}</p>
              <p className="opacity-70 mb-1">{currentSong.album}</p>
              <p className="opacity-70">{currentSong.releaseDate}</p>
            </div>
          </div>
        </div>

        <div className="mt-12 bg-white/10 backdrop-blur-lg rounded-3xl shadow-2xl p-8">
          <h2 className="text-3xl font-bold mb-6">Frequently Asked Questions</h2>
          <Accordion type="single" collapsible className="w-full">
            <AccordionItem value="item-1">
              <AccordionTrigger>What is Sunnify Spotify Downloader?</AccordionTrigger>
              <AccordionContent>
                Sunnify Spotify Downloader is a web application that allows you to process and preview your favorite Spotify playlists. Please note that this tool is for educational purposes only and should be used in compliance with copyright laws.
              </AccordionContent>
            </AccordionItem>
            <AccordionItem value="item-2">
              <AccordionTrigger>How do I use Sunnify Spotify Downloader?</AccordionTrigger>
              <AccordionContent>
                Simply paste the URL of a Spotify playlist into the input field and click the "Process Playlist" button. The app will then process each track and provide preview links.
              </AccordionContent>
            </AccordionItem>
            <AccordionItem value="item-3">
              <AccordionTrigger>Is it legal to download music from Spotify?</AccordionTrigger>
              <AccordionContent>
                Downloading copyrighted music without permission may be illegal in many jurisdictions. Sunnify Spotify Downloader is intended for educational purposes only and does not actually download music. Always ensure you have the right to access and use the music you're processing.
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        </div>

        <footer className="mt-12 text-center">
          <div className="flex justify-center space-x-4 mb-4">
            <Button 
              variant="ghost" 
              size="icon" 
              onClick={() => window.open("https://github.com/sunnypatell", "_blank")}
            >
              <Github className="h-6 w-6" />
            </Button>
            <Button 
              variant="ghost" 
              size="icon" 
              onClick={() => window.open("https://www.linkedin.com/in/sunny-patel-30b460204/", "_blank")}
            >
              <Linkedin className="h-6 w-6" />
            </Button>
            <Button 
              variant="ghost" 
              size="icon" 
              onClick={() => window.open("https://www.sunnypatel.net/", "_blank")}
            >
              <Globe className="h-6 w-6" />
            </Button>
          </div>
          <div className="text-sm opacity-70">
            <p>© 2023 Sunny Jayendra Patel. All rights reserved.</p>
            <p className="mt-2">
              ⚠️ Legal and Ethical Notice: Sunnify Spotify Downloader is intended for educational purposes only. 
              Users are responsible for complying with copyright laws and regulations in their jurisdiction. 
              This tool does not actually download music and is for demonstration purposes only.
            </p>
          </div>
        </footer>
      </div>
    </div>
  )
}
