'use client'

import React, { useState, useEffect } from 'react'
import { Sun, Music, Download, Play, Pause, RefreshCw, Github, Linkedin, Globe } from 'lucide-react'
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Progress } from "@/components/ui/progress"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import { toast, Toaster } from 'react-hot-toast'
import { FaWindows } from 'react-icons/fa'; // Import the Windows icon from react-icons


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
  const [typedText, setTypedText] = useState('')
  const [showDeveloperInfo, setShowDeveloperInfo] = useState(false)
  const [showTechInfo, setShowTechInfo] = useState(false)

  useEffect(() => {
    const text = "   Your Spotify Playlist Companion"
    let i = 0
    const typingInterval = setInterval(() => {
      if (i < text.length) {
        setTypedText(prev => prev + text.charAt(i))
        i++
      } else {
        clearInterval(typingInterval)
      }
    }, 100)

    return () => clearInterval(typingInterval)
  }, [])

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
    <div className="min-h-screen p-8 text-white bg-gradient-to-br from-purple-900 to-blue-900">
      <Toaster />
      <div className="max-w-7xl mx-auto">
        <header className="text-center mb-12 relative">
          <h1 className="text-6xl font-bold mb-4 flex items-center justify-center">
            <Sun className="text-yellow-400 mr-4 animate-spin-slow" size={64} />
            <span className="bg-clip-text text-transparent bg-gradient-to-r from-yellow-400 via-red-500 to-pink-500">
              Sunnify Spotify Downloader
            </span>
          </h1>
          <p className="text-2xl h-8 flex items-center justify-center">
            <Music className="mr-2" size={24} />
            {typedText}
          </p>
        </header>

        <div className="bg-white/20 backdrop-blur-lg rounded-3xl shadow-2xl overflow-hidden transition-all duration-300 hover:shadow-yellow-400/20">
          <div className="p-8">
            <div className="mb-6">
              <label htmlFor="playlist-url" className="block text-sm font-medium text-white mb-2">
                Spotify Playlist URL
              </label>
              <Input
                id="playlist-url"
                type="text"
                placeholder="https://open.spotify.com/playlist/..."
                value={playlistLink}
                onChange={(e) => setPlaylistLink(e.target.value)}
                className="w-full bg-white/30 text-white placeholder-white/60 border-white/30 focus:border-yellow-400 focus:ring-2 focus:ring-yellow-400 transition-all duration-300"
              />
            </div>
            <div className="mb-6">
              <label htmlFor="download-path" className="block text-sm font-medium text-white mb-2">
                Download Path
              </label>
              <Input
                id="download-path"
                type="text"
                placeholder="C:\Users\YourName\Desktop\Music"
                value={downloadPath}
                onChange={(e) => setDownloadPath(e.target.value)}
                className="w-full bg-white/30 text-white placeholder-white/60 border-white/30 focus:border-yellow-400 focus:ring-2 focus:ring-yellow-400 transition-all duration-300"
              />
            </div>
            <Button 
              onClick={handleDownload} 
              className="w-full mb-4 bg-gradient-to-r from-green-500 to-blue-500 hover:from-green-600 hover:to-blue-600 text-white font-bold py-4 rounded-full transition-all duration-300 transform hover:scale-105 focus:outline-none focus:ring-2 focus:ring-yellow-400"
              disabled={isDownloading || !downloadPath}
            >
              {isDownloading ? (
                <>
                  <RefreshCw className="mr-2 animate-spin" size={20} />
                  Processing...
                </>
              ) : (
                <>
                  <Download className="mr-2" size={20} />
                  Process Playlist
                </>
              )}
            </Button>
            <div className="mt-8">
              <h2 className="text-lg font-semibold mb-2">Processing Progress</h2>
              <Progress value={downloadProgress} className="mb-2 h-3 bg-white/20" />
              <p className="text-sm">Songs processed: {songsDownloaded}</p>
              <p className="text-sm">Playlist: {playlistName}</p>
              <p className="text-sm mt-2 italic">{statusMessage}</p>
            </div>
          </div>
        </div>

        {downloadedTracks.length > 0 && (
          <div className="mt-12 bg-white/20 backdrop-blur-lg rounded-3xl shadow-2xl p-8">
            <h2 className="text-2xl font-bold mb-4">Downloaded Tracks</h2>
            <ScrollArea className="h-64 w-full rounded-md border border-white/20 p-4">
              {downloadedTracks.map((track) => (
                <div key={track.id} className="flex items-center justify-between py-3 border-b border-white/10 last:border-b-0 hover:bg-white/10 transition-colors duration-200">
                  <div>
                    <p className="font-medium">{track.title}</p>
                    <p className="text-sm opacity-70">{track.artists}</p>
                  </div>
                  <Button variant="ghost" size="icon" onClick={() => playPauseTrack(track)} className="text-yellow-400 hover:text-yellow-300">
                    {isPlaying && currentSong.id === track.id ? <Pause size={20} /> : <Play size={20} />}
                  </Button>
                </div>
              ))}
            </ScrollArea>
          </div>
        )}

<div className="mt-12 bg-white/20 backdrop-blur-lg rounded-3xl shadow-2xl p-8 transition-all duration-300 hover:shadow-yellow-400/20">
      <h2 className="text-3xl font-bold mb-6">Download Windows App</h2>
      <p className="mb-4">
        Experience Sunnify Spotify Downloader on your Windows desktop! Download
        the app for a seamless music processing experience.
      </p>
      <a
        href="https://github.com/sunnypatell/sunnify-spotify-downloader/blob/main/dist/Sunnify%20(Spotify%20Downloader).exe"
        target="_blank"
        rel="noopener noreferrer"
        className="bg-gradient-to-r from-blue-500 to-purple-500 hover:from-blue-600 hover:to-purple-600 text-white font-bold py-2 px-4 rounded-full transition-all duration-300 transform hover:scale-105 focus:outline-none focus:ring-2 focus:ring-yellow-400 inline-flex items-center"
      >
        <FaWindows className="mr-2" size={20} /> {/* Use FaWindows icon */}
        Download for Windows
      </a>
    </div>

        <div className="mt-12 bg-white/20 backdrop-blur-lg rounded-3xl shadow-2xl p-8 transition-all duration-300 hover:shadow-yellow-400/20">
          <h2 className="text-3xl font-bold mb-6">Technology Stack</h2>
          <Button 
            onClick={() => setShowTechInfo(!showTechInfo)}
            className="mb-4 bg-gradient-to-r from-purple-500 to-indigo-500 hover:from-purple-600 hover:to-indigo-600 text-white font-bold py-2 px-4 rounded-full transition-all duration-300 transform hover:scale-105 focus:outline-none focus:ring-2 focus:ring-yellow-400"
          >
            {showTechInfo ? 'Hide Tech Info' : 'Show Tech Info'}
          </Button>
          {showTechInfo && (
            <div className="mt-4 space-y-4 animate-fadeIn">
              <h3 className="text-xl font-semibold">Frontend Technologies:</h3>
              <ul className="list-disc list-inside space-y-2">
              <li>⚛️ <strong>React:</strong> Used for building the user interface components.</li>
              <li>🚀 <strong>Next.js:</strong> Provides the framework for server-side rendering and routing.</li>
              <li>🎨 <strong>Tailwind CSS:</strong> Used for styling and responsive design.</li>
              <li>🧩 <strong>shadcn/ui:</strong> Provides pre-built, customizable UI components.</li>
              <li>🔍 <strong>Lucide React:</strong> Used for icons throughout the application.</li>
              <li>⚙️ <strong>React Hooks:</strong> Utilized for state management and side effects.</li>
              <li>🌐 <strong>Fetch API:</strong> Used for making HTTP requests to the backend.</li>
              <li>🎧 <strong>Web Audio API:</strong> Implemented for audio playback functionality.</li>
              </ul>
              <h3 className="text-xl font-semibold mt-6">Backend Technologies:</h3>
              <ul className="list-disc list-inside space-y-2">
              <li>🐍 <strong>Flask:</strong> Python web framework for creating the API endpoints.</li>
              <li>🖥️ <strong>PyQt5:</strong> Used for the GUI interface in the desktop application.</li>
              <li>🔗 <strong>Requests:</strong> Used for making HTTP requests to fetch playlist data.</li>
              <li>🕸️ <strong>BeautifulSoup:</strong> Used for web scraping and parsing HTML content.</li>
              <li>🎵 <strong>Mutagen:</strong> Used for editing ID3 tags and scraping metadata.</li>
              <li>🔓 <strong>Flask-CORS:</strong> Handles Cross-Origin Resource Sharing (CORS) for API requests.</li>
              <li>🆔 <strong>UUID:</strong> Generates unique IDs for tracks and analysis processes.</li>
              <li>🕵️‍♂️ <strong>User-Agent:</strong> Emulates real browser activity to bypass protection mechanisms.</li>
              <li>🤖 <strong>Selenium:</strong> Used for browser automation and emulating user interactions.</li>
              <li>🎥 <strong>FFmpeg:</strong> Handles audio conversion and processing.</li>
              </ul>
              <h3 className="text-xl font-semibold mt-6">Key Features:</h3>
              <ul className="list-disc list-inside space-y-2">
              <li>🔒 <strong>CORS Handling:</strong> Implemented to allow cross-origin requests securely.</li>
              <li>🆔 <strong>ID Generation:</strong> Unique IDs are generated for tracks and analysis processes.</li>
              <li>🛡️ <strong>Browser Headers Emulation:</strong> Mimics real browser headers to avoid detection.</li>
              <li>📊 <strong>Playlist Metadata Retrieval:</strong> Fetches and processes playlist information.</li>
              <li>🕸️ <strong>Web Scraping:</strong> Extracts necessary data from web pages.</li>
              <li>👨‍💻 <strong>Real Browser Activity Emulation:</strong> Simulates human-like browsing patterns.</li>
              <li>🔄 <strong>User-Agent Rotation:</strong> Regularly changes user-agent strings to avoid blocking.</li>
              <li>🛣️ <strong>Flask Routing:</strong> Handles various API endpoints for different functionalities.</li>
              <li>⚡ <strong>Asynchronous Processing:</strong> Manages concurrent downloads and processing tasks.</li>
              <li>🚨 <strong>Error Handling:</strong> Robust error management for various scenarios.</li>
              </ul>
              <p className="mt-6">
                The backend and frontend work together to provide a seamless experience. The backend handles the heavy lifting of processing Spotify playlists, while the frontend provides an intuitive user interface for interacting with the application. The frontend communicates with the backend via API calls, allowing users to initiate playlist processing and receive real-time updates on the progress.
              </p>
            </div>
          )}
        </div>

        <div className="mt-12 bg-white/20 backdrop-blur-lg rounded-3xl shadow-2xl p-8 transition-all duration-300 hover:shadow-yellow-400/20">
          <h2 className="text-3xl font-bold mb-6">Frequently Asked Questions</h2>
          <Accordion type="single" collapsible className="w-full">
            <AccordionItem value="item-1">
              <AccordionTrigger className="hover:text-yellow-400 transition-colors duration-200">What is Sunnify Spotify Downloader?</AccordionTrigger>
              <AccordionContent>
                Sunnify Spotify Downloader is a web application that allows you to process and preview your favorite Spotify playlists. It's important to note that this tool is for educational and demonstration purposes only, showcasing API integration, web scraping, proxy masking, UI design, and full-stack development skills.
              </AccordionContent>
            </AccordionItem>
            <AccordionItem value="item-2">
              <AccordionTrigger className="hover:text-yellow-400 transition-colors duration-200">How does Sunnify Spotify Downloader work?</AccordionTrigger>
              <AccordionContent>
                Sunnify Spotify Downloader uses third-party services and APIs to process Spotify playlists. It doesn't host any services to download music directly. Instead,
                it demonstrates the integration of various technologies in a full-stack project, including a backend relational database.
              </AccordionContent>
            </AccordionItem>
            <AccordionItem value="item-3">
              <AccordionTrigger className="hover:text-yellow-400 transition-colors duration-200">Is it legal to use Sunnify Spotify Downloader?</AccordionTrigger>
              <AccordionContent>
                Sunnify Spotify Downloader is intended for use with non-copyrighted music only. We do not condone or support any illegal activities. Users are responsible for ensuring they have the right to access and use any music they process through this application. Always respect copyright laws and artists' rights.
              </AccordionContent>
            </AccordionItem>
            <AccordionItem value="item-4">
              <AccordionTrigger className="hover:text-yellow-400 transition-colors duration-200">Does it work on private playlists?</AccordionTrigger>
              <AccordionContent>
                Sunnify Spotify Downloader DOES support private playlists. Although Private playlists are not accessible through the Spotify API, I'm just that guy... so feel free to scrape private playlists as well, as long as you have the URL.
              </AccordionContent>
            </AccordionItem>
            <AccordionItem value="item-5">
              <AccordionTrigger className="hover:text-yellow-400 transition-colors duration-200">What technologies are showcased in this project?</AccordionTrigger>
              <AccordionContent>
                This project demonstrates skills in API integration, web scraping, proxy masking, UI design, and full-stack development. It includes a backend with a relational database and showcases the ability to create a complete, functional web application.
              </AccordionContent>
            </AccordionItem>
            <AccordionItem value="item-6">
              <AccordionTrigger className="hover:text-yellow-400 transition-colors duration-200">Can I contribute to this project?</AccordionTrigger>
              <AccordionContent>
                While this is primarily a personal portfolio project, we welcome feedback and suggestions. If you're interested in contributing or have ideas for improvement, please reach out through the provided contact information or the GitHub repository.
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        </div>

        <div className="mt-12 bg-white/20 backdrop-blur-lg rounded-3xl shadow-2xl p-8 transition-all duration-300 hover:shadow-yellow-400/20">
          <h2 className="text-3xl font-bold mb-6">About the Developer</h2>
          <Button 
            onClick={() => setShowDeveloperInfo(!showDeveloperInfo)}
            className="mb-4 bg-gradient-to-r from-purple-500 to-indigo-500 hover:from-purple-600 hover:to-indigo-600 text-white font-bold py-2 px-4 rounded-full transition-all duration-300 transform hover:scale-105 focus:outline-none focus:ring-2 focus:ring-yellow-400"
          >
            {showDeveloperInfo ? 'Hide Info' : 'Show Info'}
          </Button>
          {showDeveloperInfo && (
            <div className="mt-4 space-y-4 animate-fadeIn">
              <p>👨‍💻 I'm a Software Engineer with over 4 years of experience in software development and cloud technologies.</p>
              <p>🎓 Currently working toward my Honours Bachelor of Science in Computer Science at Ontario Tech University, I'm all about building reliable, scalable software that makes a difference. 💪</p>
              <p>🛠 From full-stack development to cloud-based solutions, I've led enterprise-level projects that streamline operations and deliver real impact.</p>
              <p>🔧 I enjoy automating workflows, optimizing systems, and turning complex challenges into real results. 📈</p>
              <p>💡 I'm always curious and constantly learning.</p>
            </div>
          )}
        </div>

        <div className="mt-12 bg-white/20 backdrop-blur-lg rounded-3xl shadow-2xl p-8 transition-all duration-300 hover:shadow-yellow-400/20">
          <h2 className="text-3xl font-bold mb-6">Legal and Ethical Notice</h2>
          <p className="mb-4">
            ⚖️ Sunnify (Spotify Downloader) is intended for educational purposes only. It is your responsibility to ensure that you comply with copyright laws and regulations in your country or region. Downloading copyrighted music without proper authorization may be illegal in certain jurisdictions.
          </p>
          <h3 className="text-2xl font-bold mb-4">License</h3>
          <p className="mb-4">
            Sunnify (Spotify Downloader) is licensed under a custom license. You can view the full license <a href="https://github.com/sunnypatell/sunnify-spotify-downloader/blob/main/LICENSE" target="_blank" rel="noopener noreferrer" className="text-yellow-400 hover:text-yellow-300 underline">here</a>.
          </p>
          <p>
            Key points of the license:
          </p>
          <ul className="list-disc list-inside mt-2 space-y-2">
            <li>The software is provided free of charge for personal or organizational use only.</li>
            <li>The software must not be modified or altered.</li>
            <li>The software must be distributed free of charge and not sold for profit.</li>
            <li>Proper attribution to the original author, Sunny Patel, must be maintained.</li>
          </ul>
          <p className="mt-4">
            For any inquiries regarding modification of the Software, please contact Sunny Patel at sunnypatel124555@gmail.com.
          </p>
        </div>

        <footer className="mt-12 text-center">
          <div className="text-sm opacity-70 mb-6">
            <p>© 2024 Sunny Jayendra Patel. All rights reserved.</p>
          </div>
          <div className="flex justify-center space-x-4">
            <a href="https://github.com/sunnypatell/sunnify-spotify-downloader" target="_blank" rel="noopener noreferrer">
              <Button variant="outline" size="icon" className="bg-white/10 hover:bg-white/20">
                <Github className="h-5 w-5" />
              </Button>
            </a>
            <a href="https://www.linkedin.com/in/sunny-patel-30b460204/" target="_blank" rel="noopener noreferrer">
              <Button variant="outline" size="icon" className="bg-white/10 hover:bg-white/20">
                <Linkedin className="h-5 w-5" />
              </Button>
            </a>
            <a href="https://www.sunnypatel.net/" target="_blank" rel="noopener noreferrer">
              <Button variant="outline" size="icon" className="bg-white/10 hover:bg-white/20">
                <Globe className="h-5 w-5" />
              </Button>
            </a>
          </div>
        </footer>
      </div>
    </div>
  )
}