from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict
from core.classes.utils.utils_os import UtilsOS

class EnvironmentVariables(BaseSettings):
  """Environment Variables, read from .env file or environment variables"""
  model_config = SettingsConfigDict(
    env_file=".env",
    case_sensitive=True,
  )
  BACKEND_PORT: int
  FRONTEND_PORT: int
  STATIC_DIR_TO_SERVE_PATH: str | None = None
  LOG_LEVEL: Literal["debug", "info"]
    
class AppConfigRuntime():
  """App Config part of runtime stuff"""
  def __init__(self, envVars: EnvironmentVariables):
    self.binaries_path: Path = Path.cwd() / ".bin"
    self.user_config_dir_path: Path = Path(UtilsOS.getUserAppDataDirectoryPath()) / "Sunnify"
    self.user_config_file_path: Path = Path(UtilsOS.getUserAppDataDirectoryPath()) / "Sunnify" / "config--for-react-app.json"
    self.cors_origins: list[str] = [
      f"http://localhost:{envVars.FRONTEND_PORT}",
    ]
  def dump(self):
    return {
      "binaries_path": str(self.binaries_path),
      "user_config_dir_path": str(self.user_config_dir_path),
      "user_config_file_path": str(self.user_config_file_path),
      "cors_origins": self.cors_origins
    }

class AppConfig():
  """App Config"""
  def __init__(
    self,
    envVars: EnvironmentVariables,
    runtime: AppConfigRuntime,
  ):
    self.envVars: EnvironmentVariables = envVars
    self.runtime: AppConfigRuntime = runtime