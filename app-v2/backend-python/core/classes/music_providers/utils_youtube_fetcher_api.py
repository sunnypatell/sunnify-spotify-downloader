import yt_dlp
from models.new import TrackDerived
from core.singleton.logger import logger
from core.singleton.native_deps_checker import nativeDepsChecker
from core.classes.music_providers.utils_youtube import UtilsYoutube
from core.classes.utils.utils_disk import UtilsDisk

class UtilsYoutubeFetcherApi:
  @staticmethod
  def findYoutubeUrlOfTrack(trackDerived: TrackDerived) -> str | None:
    """Find YouTube URL of track (Auto-Search URL)"""
    # define search query
    searchQuery = f"{trackDerived.artists} {trackDerived.title}"
    
    # init client options
    ydl_opts: yt_dlp._Params = {
      'quiet': True,
      'no_warnings': True,
      'default_search': 'ytsearch1',  # Retutns only first match
      'extract_flat': 'in_playlist',
    }
    
    # search
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
      info = ydl.extract_info(
        searchQuery,
        download=False
      )
            
    # extract the first track found
    if info and 'entries' in info and len(info['entries']) > 0:
      first_result = info['entries'][0]
      itemData ={
        'video_url': f"https://www.youtube.com/watch?v={first_result['id']}",
        'title': first_result.get('title', 'Unknown'),
        'duration': first_result.get('duration', 0),
      }
      return itemData['video_url']
    else:
      return None
  
  @staticmethod
  def downloadYoutubeTrackAsMp3(trackDerived: TrackDerived):
    """Download track from YouTube as MP3 and save to disk"""
    
    # ensure ffmpeg is installed
    ffmpegPath = nativeDepsChecker.getFFmpegPath()
    if not ffmpegPath:
      return (False, "FFMPEG_NOT_INSTALLED")
    
    # ensure deno is installed
    denoPath = nativeDepsChecker.getDenoPath()
    if not denoPath:
      return (False, "DENO_NOT_INSTALLED")

    # get track data
    rawYoutubeUrl = trackDerived.youtube_url
    diskFilePathWithoutExtension = trackDerived.disk_file_path_without_extension
    diskDirPath = UtilsDisk.deriveDirPathFromFilePath(diskFilePathWithoutExtension)
    
    # maybe create playlist dir
    UtilsDisk.createDirIfNotExists(diskDirPath)

    # if no URL found, return
    if not rawYoutubeUrl:
      return (False, "NO_YOUTUBE_URL")
    
    # if disk path is not accessible, return
    if not UtilsDisk.checkIfFolderIsWritable(diskDirPath):
      return (False, "DISK_PATH_NOT_ACCESSIBLE")

    # clean up URL
    youtubeUrl = UtilsYoutube.cleanYoutubeVideoUrl(rawYoutubeUrl)
    
    # download
    try:
      ydl_opts: yt_dlp._Params = {
        'format': 'bestaudio/best',
        'postprocessors': [{
          'key': 'FFmpegExtractAudio',
          'preferredcodec': 'mp3',
          'preferredquality': '320',
        }],
        'outtmpl': diskFilePathWithoutExtension,
        'quiet': False,
        'no_warnings': False,
        'retries': 5,
        'socket_timeout': 15,
        'noplaylist': True,
        # 'verbose': True,
        'js_runtimes': {
          'deno': {'path': str(denoPath)},
          'node': {'path': None}
        },
        'ffmpeg_location': str(ffmpegPath)
      }
      with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.extract_info(youtubeUrl, download=True)
        return (True,"SUCCESS")
    except Exception as e:
      logger.error(f"Download failed: {e}")
      return (False,"ERROR_DOWNLOADING", [e])
    
    