import os
import sys
import yt_dlp
from models.new import TrackDerived
from core.singleton.logger import logger
from core.singleton.app_config import appConfig
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
    if not UtilsFFMPEG.getFFmpegPath():
      return (False, "FFMPEG_NOT_INSTALLED")
    
    # ensure deno is installed
    denoPath = UtilsDeno.getDenoPath()
    if not denoPath:
      return (False, "DENO_NOT_INSTALLED")

    # get track data
    rawYoutubeUrl = trackDerived.youtube_url
    diskFilePathWithoutExtension = trackDerived.disk_file_path_without_extension

    # if no URL found, return
    if not rawYoutubeUrl:
      return (False, "NO_YOUTUBE_URL")
    
    # if disk path is not accessible, return
    if not UtilsDisk.getFolderIsWritable(diskFilePathWithoutExtension):
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
        }
      }
      with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.extract_info(youtubeUrl, download=True)
        return (True,"SUCCESS")
    except Exception as e:
      logger.error(f"Download failed: {e}")
      return (False,"ERROR_DOWNLOADING", e)
    
    
class UtilsDeno:
  @staticmethod
  def getDenoPath():
    denoPath = appConfig.runtime.binaries_path / "deno"
    logger.info(f"denoPath: {denoPath}")
    if os.path.exists(denoPath):
      return denoPath
    return None
    
class UtilsFFMPEG:
  @staticmethod
  def getFFmpegPath():
    """Get path to FFmpeg - checks bundled first, then system paths."""
    # Check bundled FFmpeg first (for PyInstaller builds)
    if getattr(sys, "frozen", False):
        base_path = sys._MEIPASS
        if sys.platform == "win32":
            ffmpeg = os.path.join(base_path, "ffmpeg", "ffmpeg.exe")
        else:
            ffmpeg = os.path.join(base_path, "ffmpeg", "ffmpeg")
        if os.path.exists(ffmpeg):
            return os.path.join(base_path, "ffmpeg")

    # Check common system paths (for homebrew/system installs)
    ffmpeg_name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    common_paths = [
        "/opt/homebrew/bin",  # macOS ARM homebrew
        "/usr/local/bin",  # macOS Intel homebrew / Linux
        "/usr/bin",  # Linux system
    ]

    for path in common_paths:
        ffmpeg = os.path.join(path, ffmpeg_name)
        if os.path.exists(ffmpeg):
            return path

    # Check if ffmpeg is in PATH
    import shutil

    ffmpeg_in_path = shutil.which("ffmpeg")
    if ffmpeg_in_path:
        return os.path.dirname(ffmpeg_in_path)

    return None