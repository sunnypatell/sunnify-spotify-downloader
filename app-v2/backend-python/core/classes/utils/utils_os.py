import os
import sys
from typing import Literal


class UtilsOS:
  """Utils for OS detection"""
  @staticmethod
  def getOsType() -> Literal["MAC_OS", "WINDOWS", "LINUX"]:
    # Mac
    if sys.platform == "darwin":  
      return "MAC_OS"
    # Windows
    elif sys.platform == "win32":  
      return "WINDOWS"
    # Linux
    else: 
      return "LINUX"
    
  @staticmethod
  def getUserHomeDirectoryPath():
    """Return the user's home directory path.  
    Mac: `/Users/username`  
    Windows: `C:/Users/username`  
    Linux: `/home/username`  
    """
    return os.path.expanduser("~")
  
  @staticmethod
  def getUserAppDataDirectoryPath():
    """Return the user's app data directory path.  
    Mac: `/Users/username/Library/Application Support`  
    Windows: `C:/Users/username/AppData`  
    Linux: `/home/username/.config`
    """
    osName = UtilsOS.getOsType()
    homeDirPath = UtilsOS.getUserHomeDirectoryPath()
    base: str
    if osName == "MAC_OS":
      base = os.path.join(homeDirPath, "Library", "Application Support")
    elif osName == "WINDOWS":
      base = os.environ.get("APPDATA", homeDirPath)
    else:
      base = os.environ.get("XDG_CONFIG_HOME", os.path.join(homeDirPath, ".config"))
    return base