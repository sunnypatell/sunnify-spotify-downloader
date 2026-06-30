from pathlib import Path
from mutagen.mp3 import MP3
from mutagen.m4a import M4A
from mutagen.flac import FLAC

from models.new import PlaylistRaw, TrackRaw, TrackDerived
from core.classes.data.user_config_api import UserConfigApi

class UtilsTrackDisk:
  @staticmethod 
  def deriveTrackFileName(title: str, artists: str, index: int, userConfigApi: UserConfigApi):
    """Calculate track file name from track metadata (title, artist, index)"""
    fileNamePattern = userConfigApi.config_as_object.setting_disk_filename_pattern
    fileExtension = userConfigApi.config_as_object.setting_disk_format
    
    # define a map for all replacements
    title_subs  = {
      "/": "",
      "\\": "",
      ":": "",
      "*": "",
      "?": "",
      "\"": "",
      "<": "",
      ">": "",
      "|": "",
      "'": "",
      "!": "",
      ",": "",
    }
    artists_subs  = {
      "/": "",
      "\\": "",
      ":": "",
      "*": "",
      "?": "",
      "\"": "",
      "<": "",
      ">": "",
      "|": "",
      ",": "",
      "'": "",
      " & ": " ",
      "&": "",
    }
    pattern_subs = {
      "title": "{title}",
      "artist": "{artist}",
      "index": "{index}",
    }
    
    # normalize parts
    clean_title = title
    for k,v in title_subs.items():
      clean_title = clean_title.replace(k,v)
    
    clean_artist = artists
    for k,v in artists_subs.items():
      clean_artist = clean_artist.replace(k,v)

    clean_index = str(index+1).zfill(2)
    clean_extension = "." + fileExtension.replace(".","")
    
    # replace pattern with parts
    finalName = fileNamePattern
    finalName = finalName.replace(pattern_subs['title'], clean_title)
    finalName = finalName.replace(pattern_subs['artist'], clean_artist)
    finalName = finalName.replace(pattern_subs['index'], clean_index)
    
    finalNameWithoutExtension = finalName
    finalNameWithExtension = finalNameWithoutExtension + clean_extension
    
    return (finalNameWithExtension, finalNameWithoutExtension)
  
  @staticmethod
  def deriveTrackRawFileName(trackRaw: TrackRaw, index: int, userConfigApi: UserConfigApi): 
    """Calculate track file name from TrackRaw"""
    fileNameWithExtension, fileNameWithoutExtension = UtilsTrackDisk.deriveTrackFileName(
      title=trackRaw.title,
      artists=trackRaw.artists,
      index=index,
      userConfigApi=userConfigApi
    )
    return (fileNameWithExtension, fileNameWithoutExtension)
  
  @staticmethod
  def derivePlaylistPath(playlistRaw: PlaylistRaw, userConfigApi: UserConfigApi) -> str:
    """Calculate playlist path from PlaylistRaw"""
    clean_name = playlistRaw.name.replace("/","").replace("\\","").replace(":","").replace("*","").replace("?","").replace("\"","").replace("<","").replace(">","").replace("|","").replace("'","")
    base_path = userConfigApi.config_as_object.setting_disk_download_path
    return base_path + "/" + clean_name
  
  @staticmethod
  def deriveTrackFilePath(trackRaw: TrackRaw, index: int, playlistRaw: PlaylistRaw, userConfigApi: UserConfigApi):
    """Calculate track file path (absolute path) from TrackRaw and PlaylistRaw"""
    playlistPath = UtilsTrackDisk.derivePlaylistPath(playlistRaw, userConfigApi)
    fileNameWithExtension, fileNameWithoutExtension = UtilsTrackDisk.deriveTrackRawFileName(trackRaw, index, userConfigApi)
    finalPathWithExtension = playlistPath + "/" + fileNameWithExtension
    finalPathWithoutExtension = playlistPath + "/" + fileNameWithoutExtension
    return (finalPathWithExtension, finalPathWithoutExtension)
  
  @staticmethod
  def deriveTrackAudioDurationMs(trackRaw: TrackRaw, index: int, playlistRaw: PlaylistRaw, userConfigApi: UserConfigApi) -> int:
    """Calculate track audio duration in ms from TrackRaw and PlaylistRaw, returns 0 if file does not exist"""
    # get file
    fileNameString = UtilsTrackDisk.deriveTrackRawFileName(
      trackRaw=trackRaw,
      index=index,
      userConfigApi=userConfigApi
    )[0]
    finalPathString = UtilsTrackDisk.deriveTrackFilePath(
      trackRaw=trackRaw,
      index=index,
      playlistRaw=playlistRaw,
      userConfigApi=userConfigApi
    )[0]
    finalPath = Path(finalPathString).expanduser()
    
    if not finalPath.exists():
      return 0

    duration_sec: int = 0
    ext = fileNameString.split(".")[-1]
    try:
      if ext == 'mp3':
        audio = MP3(finalPath)
        duration_sec = audio.info.length
      elif ext in ['m4a', 'mp4']:
        audio = M4A(finalPath)
        duration_sec = audio.info.length
      elif ext == 'flac':
        audio = FLAC(finalPath)
        duration_sec = audio.info.length
      else:
        return 0
      if duration_sec:
        duration_sec = int(duration_sec * 1000)
      else:
        duration_sec = 0
      return duration_sec
    except Exception:
        return 0
  
  @staticmethod
  def deleteTrackFile(trackDerived: TrackDerived):
    """Delete track file from disk"""
    finalPath = Path(trackDerived.disk_file_path)
    
    # if no file
    if not finalPath.exists():
      return "FILE_NOT_FOUND"
    
    # delete file from disk
    try:
      finalPath.unlink()
    except Exception:
      return "FILE_DELETE_ERROR"
    
    # return
    return "SUCCESS"