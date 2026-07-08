import os
from pathlib import Path
import subprocess
from core.singleton.logger import logger
from core.classes.utils.utils_os import UtilsOS
    
class UtilsDisk:
  """Utilities for working with the OS disk"""
  @staticmethod
  def revealInFinder(dirOrFilePath: str) -> None:
    """Reveal directory/file in OS finder"""
    osType = UtilsOS.getOsType()
    path = Path(dirOrFilePath).resolve()
    # macOS
    if osType == "MAC_OS":  
      subprocess.run(["open", "-R", str(path)])
    # Windows
    elif osType == "WINDOWS":  
      subprocess.run(["explorer", "/select,", str(path)])
    # Linux
    else: 
      subprocess.run(["xdg-open", str(path.parent)])
      
  @staticmethod
  def checkIfFileExists(filePath: str) -> bool:
    """Check if file exists on disk"""
    return Path(filePath).expanduser().exists()
    
  @staticmethod
  def checkIfDirExists(dirPath: str) -> bool:
    """Check if directory exists on disk"""
    exists = Path(dirPath).expanduser().exists()
    if not exists:
      logger.info(f"checkIfDirExists - path: {dirPath} - does not exist")
      return False
    logger.info(f"checkIfDirExists - path: {dirPath} - exists")
    return True
    # return os.path.exists(dirPath)
      
  @staticmethod
  def checkIfFolderIsWritable(folderPath: str) -> bool:
    """Check if folder is writable"""
    exists = UtilsDisk.checkIfDirExists(folderPath)
    if not exists:
      return False
    isWritable = os.access(folderPath, os.W_OK)
    return isWritable
    
  @staticmethod
  def deriveDirPathFromFilePath(filePath: str):
    """Derive directory path from file path. E.g. /path/to/file.txt -> /path/to"""
    return str(Path(filePath).parent)
  
  @staticmethod
  def createDirIfNotExists(dirPath: str):
    """Create directory if it does not exist"""
    Path(dirPath).mkdir(parents=True, exist_ok=True)
    
  @staticmethod
  def deleteFileIfExists(filePath: str):
    """Delete file if it exists"""
    if os.path.exists(filePath):
      os.remove(filePath)
      
  @staticmethod
  def makeExecutable(filePath: str):
    """Make file executable"""
    os.chmod(filePath, 0o755)