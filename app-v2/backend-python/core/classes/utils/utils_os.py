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