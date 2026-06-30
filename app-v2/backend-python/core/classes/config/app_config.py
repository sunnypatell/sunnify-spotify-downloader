import os
from pathlib import Path
import sys
from pydantic_settings import BaseSettings

# constants
USER_CONFIG_FILE_NAME = "config--for-react-app.json"

class UserConfigFilePathApi():
  """API for getting the path to the user config file based on OS"""
  
  @staticmethod
  def get_dir_path() -> Path:
    """Return the per-user config directory, creating it if needed."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    elif sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME", os.path.join(os.path.expanduser("~"), ".config"))
    configDir = Path(base) / "Sunnify"
    configDir.mkdir(parents=True, exist_ok=True)
    return configDir
  
  @staticmethod
  def get_file_path() -> Path:
    """Return the absolute path to config.json"""
    finalPath = UserConfigFilePathApi.get_dir_path() / USER_CONFIG_FILE_NAME
    return finalPath


class AppConfigRuntime():
  """App Config part of runtime stuff"""
  # props
  binaries_path: Path = Path.cwd() / ".bin"
  download_path = Path("~/Music/Sunnify").expanduser()
  user_config_file_path: Path = UserConfigFilePathApi.get_file_path()

class AppConfigStatic(BaseSettings):
  """App Config part of static stuff, derived from .env file"""
  # Spotify
  spotify_client_id: str = ""
  spotify_client_secret: str = ""

  # Server
  debug: bool = True
  log_level: str = "info"
  backend_port: int = 8000
  cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

  class Config:
    env_file = ".env"
    case_sensitive = False


class AppConfig():
  """App Config"""
  def __init__(
    self,
    static: AppConfigStatic,
    runtime: AppConfigRuntime,
  ):
    self.static: AppConfigStatic = static
    self.runtime: AppConfigRuntime = runtime