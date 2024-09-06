'use client'

import React, { useState, useEffect } from 'react'
import { Sun, Music, Download, Play, Pause, Folder, X } from 'lucide-react'
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
  const [downloadPath, setDownloadPath] = useState('')

  const handleDownload = async () => {
    if (!playlistLink) {
      toast.error('Please enter a valid Spotify playlist URL')
      return
    }

    if (!downloadPath) {
      toast.error('Please enter a download location')
      return
    }

    setIsDownloading(true)
    setDownloadProgress(0)
    setSongsDownloaded(0)
    setStatusMessage("Starting download...")
    setDownloadedTracks([])

    try {
      const response = await fetch('http://localhost:5000/api/scrape-playlist', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          playlistUrl: playlistLink,
          downloadPath: downloadPath
        }),
      })

      const reader = response.body!.getReader()
      const decoder = new TextDecoder()

      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        
        const events = decoder.decode(value).split('\n\n')
        for (const event of events) {
          if (event.startsWith('data: ')) {
            try {
              const data = JSON.parse(event.slice(6))
              switch (data.event) {
                case 'progress':
                  setDownloadProgress(data.data.progress)
                  setSongsDownloaded(prev => prev + 1)
                  setStatusMessage(`Processing: ${data.data.currentTrack.title} - ${data.data.currentTrack.artists}`)
                  break
                case 'error':
                  toast.error(data.data.message)
                  break
                case 'complete':
                  setPlaylistName(data.data.playlistName)
                  setDownloadedTracks(data.data.tracks)
                  setStatusMessage("Processing completed!")
                  toast.success("Playlist processing completed!")
                  break
              }
            } catch (parseError) {
              console.error('Error parsing event:', parseError)
            }
          }
        }
      }
    } catch (error) {
      console.error('Error:', error)
      toast.error('An error occurred while processing the playlist')
    } finally {
      setIsDownloading(false)
    }
  }

  const playPauseTrack = (track: Track) => {
    if (isPlaying && currentSong.id === track.id) {
      setIsPlaying(false)
    } else {
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
              <Input
                type="text"
                placeholder="Enter download path (e.g., C:\Users\YourName\Desktop\Music)"
                value={downloadPath}
                onChange={(e) => setDownloadPath(e.target.value)}
                className="mb-4 bg-white/20 text-white placeholder-white/60"
              />
              <Button 
                onClick={handleDownload} 
                className="w-full mb-4 bg-green-500 hover:bg-green-600 text-white"
                disabled={isDownloading || !downloadPath}
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