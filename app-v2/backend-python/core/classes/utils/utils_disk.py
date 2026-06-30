import os
from pathlib import Path
import subprocess
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
  def getFolderIsWritable(folderPath: str) -> bool:
    """Check if folder is writable"""
    return not os.access(folderPath, os.W_OK)
  
  @staticmethod
  def checkIfFileExists(filePath: str) -> bool:
    """Check if file exists on disk"""
    return Path(filePath).expanduser().exists()
    # return os.path.exists(filePath)