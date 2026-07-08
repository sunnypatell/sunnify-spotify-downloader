import os
import shutil
import sys
import platform
from typing import Literal
import urllib.request
from pathlib import Path
import urllib

from core.singleton.logger import logger
from core.classes.utils.utils_disk import UtilsDisk

class UtilsNativeDepsChecker:
  """
  Class for checking Native Deps (ffmpeg, deno) installation status and trying to download them if missing.
  
  Native Deps are used by other classes
  """
  location1LocalBinFolderPath: Path
  def __init__(
    self,
    location1LocalBinFolderPath: str
  ):
    self.location1LocalBinFolderPath = Path(location1LocalBinFolderPath)
    
  def checkAllDepsPresenceAndDownloadThemIfMissing(self):
    """Check that `ffmpeg`, `deno` are installed. If not installed, download them."""
    
    # init downloader
    downloader = UtilsNativeDepsDownloader(
      binFolderPath=str(self.location1LocalBinFolderPath)
    )
    
    # 1. check FFmpeg
    ffmpegPath = self.getFFmpegPath()
    if ffmpegPath:
      logger.info(f"FFmpeg already installed at: {ffmpegPath}")
    else:
      logger.info("FFmpeg not found, downloading...")
      downloader.downloadFFmpeg()
      downloader.downloadFFprobe()
      ffmpegPath = self.getFFmpegPath()
      if not ffmpegPath:
        raise RuntimeError("FFmpeg not found, tried to download but failed!")
      
    # 2. check Deno
    denoPath = self.getDenoPath()
    if denoPath:
      logger.info(f"Deno already installed at: {denoPath}")
    else:
      logger.info("Deno not found, downloading...")
      downloader.downloadDeno()
      denoPath = self.getDenoPath()
      if not denoPath:
        raise RuntimeError("Deno not found, tried to download but failed!")
  
  def getFFmpegPath(self):
    """Get path to FFmpeg."""
    
    logger.info(f"getFFmpegPath...")
    # Get executable name based on OS
    ffmpegExecutableName = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    
    # 1. Check local .bin folder
    logger.info(f"Location 1 (local bin folder)...")
    dirPath = self.location1LocalBinFolderPath
    ffmpegPath = dirPath / ffmpegExecutableName
    logger.info(f"- Path: {ffmpegPath}")
    if os.path.exists(ffmpegPath):
      logger.info(f"  - Found: {ffmpegPath}")
      return str(ffmpegPath)
    logger.info(f"  - Not found")
    
    # 2. Check bundled FFmpeg first (for PyInstaller builds)
    logger.info(f"Location 2 (bundled with PyInstaller)...")
    if getattr(sys, "frozen", False):
      dirPath = sys._MEIPASS
      if sys.platform == "win32":
        ffmpegPath = os.path.join(dirPath, "ffmpeg", ffmpegExecutableName)
      else:
        ffmpegPath = os.path.join(dirPath, "ffmpeg", ffmpegExecutableName)
      logger.info(f"- Path: {ffmpegPath}")
      if os.path.exists(ffmpegPath):
        logger.info(f"  - Found: {ffmpegPath}")
        return os.path.join(dirPath, "ffmpeg")
    else:
      logger.info(f"  - Skipped, is not PyInstaller build")
        
    # 3. Check common system paths (for homebrew/system installs)
    logger.info(f"Location 3 (common system paths)...")
    commonSystemPaths = [
      "/opt/homebrew/bin",  # macOS ARM homebrew
      "/usr/local/bin",  # macOS Intel homebrew / Linux
      "/usr/bin",  # Linux system
    ]
    for dirPath in commonSystemPaths:
      ffmpegPath = os.path.join(dirPath, ffmpegExecutableName)
      logger.info(f"- Path: {ffmpegPath}")
      if os.path.exists(ffmpegPath):
        logger.info(f"  - Found: {ffmpegPath}")
        return ffmpegPath
      else:
        logger.info(f"  - Not found")

    # 4. Check if ffmpeg is in PATH (bin is in unknown path but ffmpeg is in PATH)
    logger.info(f"Location 4 (ffmpeg in PATH)...")
    ffmpegInPath = shutil.which("ffmpeg")
    if ffmpegInPath:
      logger.info(f"  - Found: {ffmpegInPath}")
      return os.path.dirname(ffmpegInPath)
    logger.info(f"  - Not found")

    return None
  
  def getDenoPath(self):
    logger.info(f"getDenoPath...")
    
    # Get executable name based on OS
    denoExecutableName = "deno.exe" if sys.platform == "win32" else "deno"
    
    # 1. Check local .bin folder
    logger.info(f"Location 1 (local bin folder)...")
    dirPath = self.location1LocalBinFolderPath
    denoPath = dirPath / denoExecutableName
    logger.info(f"- Path: {denoPath}")
    if os.path.exists(denoPath):
      logger.info(f"  - Found: {denoPath}")
      return denoPath
    logger.info(f"  - Not found")
    
    return None
  
  
class UtilsNativeDepsDownloader:
  binFolderPath: str
  def __init__(self, binFolderPath: str):
    self.binFolderPath = binFolderPath
  
  def downloadDeno(self):
    """Download Deno"""
    return UtilsBinaryDownloader.downloadBinaryFileToPathBasedOnOs(
      destinationDirPath=str(self.binFolderPath),
      URL_MAC_ARM64="https://github.com/denoland/deno/releases/download/v2.8.2/deno-aarch64-apple-darwin.zip",
      URL_MAC_X64="https://github.com/denoland/deno/releases/download/v2.8.2/deno-x86_64-apple-darwin.zip",
      URL_LINUX_ARM64="https://github.com/denoland/deno/releases/download/v2.8.2/deno-aarch64-unknown-linux-gnu.zip",
      URL_LINUX_X64="https://github.com/denoland/deno/releases/download/v2.8.2/deno-x86_64-unknown-linux-gnu.zip",
      URL_WIN_ARM64="https://github.com/denoland/deno/releases/download/v2.8.2/deno-aarch64-pc-windows-msvc.zip",
      URL_WIN_X64="https://github.com/denoland/deno/releases/download/v2.8.2/deno-x86_64-pc-windows-msvc.zip",
      BIN_NAME_MAC="deno",
      BIN_NAME_LINUX="deno",
      BIN_NAME_WIN="deno.exe",
    )
    
  def downloadFFmpeg(self):
    """Download FFmpeg"""
    return UtilsBinaryDownloader.downloadBinaryFileToPathBasedOnOs(
      destinationDirPath=str(self.binFolderPath),
      URL_MAC_ARM64="https://github.com/eugeneware/ffmpeg-static/releases/download/b6.1.1/ffmpeg-darwin-arm64",
      URL_MAC_X64="https://github.com/eugeneware/ffmpeg-static/releases/download/b6.1.1/ffmpeg-darwin-x64",
      URL_LINUX_ARM64="https://github.com/eugeneware/ffmpeg-static/releases/download/b6.1.1/ffmpeg-linux-arm64",
      URL_LINUX_X64="https://github.com/eugeneware/ffmpeg-static/releases/download/b6.1.1/ffmpeg-linux-x64",
      URL_WIN_ARM64="https://github.com/eugeneware/ffmpeg-static/releases/download/b6.1.1/ffmpeg-win32-x64",
      URL_WIN_X64="https://github.com/eugeneware/ffmpeg-static/releases/download/b6.1.1/ffmpeg-win32-x64",
      BIN_NAME_MAC="ffmpeg",
      BIN_NAME_LINUX="ffmpeg",
      BIN_NAME_WIN="ffmpeg.exe",
    )
  
  def downloadFFprobe(self):
    """Download FFprobe"""
    return UtilsBinaryDownloader.downloadBinaryFileToPathBasedOnOs(
      destinationDirPath=str(self.binFolderPath),
      URL_MAC_ARM64="https://github.com/eugeneware/ffmpeg-static/releases/download/b6.1.1/ffprobe-darwin-arm64",
      URL_MAC_X64="https://github.com/eugeneware/ffmpeg-static/releases/download/b6.1.1/ffprobe-darwin-x64",
      URL_LINUX_ARM64="https://github.com/eugeneware/ffmpeg-static/releases/download/b6.1.1/ffprobe-linux-arm64",
      URL_LINUX_X64="https://github.com/eugeneware/ffmpeg-static/releases/download/b6.1.1/ffprobe-linux-x64",
      URL_WIN_ARM64="https://github.com/eugeneware/ffmpeg-static/releases/download/b6.1.1/ffprobe-win32-x64",
      URL_WIN_X64="https://github.com/eugeneware/ffmpeg-static/releases/download/b6.1.1/ffprobe-win32-x64",
      BIN_NAME_MAC="ffprobe",
      BIN_NAME_LINUX="ffprobe",
      BIN_NAME_WIN="ffprobe.exe",
    )
  
  
class UtilsBinaryDownloader:
  @staticmethod
  def downloadBinaryFileToPathBasedOnOs(
    destinationDirPath: str,
    URL_MAC_ARM64: str,
    URL_MAC_X64: str,
    URL_LINUX_ARM64: str,
    URL_LINUX_X64: str,
    URL_WIN_ARM64: str,
    URL_WIN_X64: str,
    BIN_NAME_MAC: str,
    BIN_NAME_LINUX: str,
    BIN_NAME_WIN: str,
  ): 
    """Download binary file to path based on OS, and make it executable"""
    
    # 1. derive OS and ARCH
    osName = platform.system()
    archName = platform.machine()
    logger.info(f"OS: {osName}\nARCH: {archName}")
    
    # 2. derive url, bin file name, 
    URL: str | None = None
    BIN_FILE_NAME: str | None = None
    if osName == "Darwin" and archName == "arm64":
      URL = URL_MAC_ARM64
      BIN_FILE_NAME = BIN_NAME_MAC
    elif osName == "Darwin" and archName == "x86_64":
      URL = URL_MAC_X64
      BIN_FILE_NAME = BIN_NAME_MAC
    elif osName == "Windows" and archName == "ARM64":
      URL = URL_WIN_ARM64
      BIN_FILE_NAME = BIN_NAME_WIN
    elif osName == "Windows" and archName == "AMD64":
      URL = URL_WIN_X64
      BIN_FILE_NAME = BIN_NAME_WIN
    elif osName == "Linux" and archName == "aarch64":
      URL = URL_LINUX_ARM64
      BIN_FILE_NAME = BIN_NAME_LINUX
    elif osName == "Linux" and archName == "x86_64":
      URL = URL_LINUX_X64
      BIN_FILE_NAME = BIN_NAME_LINUX
    
    if not URL:
      return (False, "UNSUPPORTED_OS", f"OS: {osName} ARCH: {archName}")
    if not BIN_FILE_NAME:
      return (False, "UNSUPPORTED_OS", f"OS: {osName} ARCH: {archName}")
    
    logger.info(f"URL: {URL}\nBIN_FILE_NAME: {BIN_FILE_NAME}")
    
    # 3. derive compression based on download url extension
    FILE_COMPRESSION: Literal["",".gz", ".zip", ".tar.gz"] = ""
    if URL.endswith(".gz"): FILE_COMPRESSION = ".gz"
    elif URL.endswith(".zip"): FILE_COMPRESSION = ".zip"
    elif URL.endswith(".tar.gz"): FILE_COMPRESSION = ".tar.gz"
    logger.info(f"FILE_COMPRESSION: {FILE_COMPRESSION or 'NO_COMPRESSION'}")
    
    # 4. create dir if not exists
    DOWNLOAD_DIR_PATH = Path(destinationDirPath)
    UtilsDisk.createDirIfNotExists(str(DOWNLOAD_DIR_PATH))
    
    # 5. download file
    DOWNLOAD_FILE_PATH = DOWNLOAD_DIR_PATH / f"{BIN_FILE_NAME}{FILE_COMPRESSION}"
    try:
      urllib.request.urlretrieve(
        url=URL,
        filename=str(DOWNLOAD_FILE_PATH)
      )
    except Exception as e:
      logger.error(f"Failed to download file\nError: {e}")
      return (False, "FAILED_TO_DOWNLOAD", e)
    
    # 5. uncompress (if compressed)
    if FILE_COMPRESSION:
      logger.info(f"Uncompressing file: {DOWNLOAD_FILE_PATH}")
      try:
        shutil.unpack_archive(
          filename=str(DOWNLOAD_FILE_PATH),
          extract_dir=str(DOWNLOAD_DIR_PATH)
        )
        UtilsDisk.deleteFileIfExists(
          filePath=str(DOWNLOAD_FILE_PATH)
        )
      except Exception as e:
        logger.error(f"Failed to uncompress file\nError: {e}")
        return (False, "FAILED_TO_UNCOMPRESS", e)
      
    # 5. make executable
    BIN_FILE_PATH = DOWNLOAD_DIR_PATH / BIN_FILE_NAME
    logger.info(f"Making executable: {BIN_FILE_PATH}")
    UtilsDisk.makeExecutable(filePath=str(BIN_FILE_PATH))
    
    # 6. success
    return (True, "OK", BIN_FILE_PATH)
    