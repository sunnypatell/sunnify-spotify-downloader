from typing import Literal, Optional, Union
from typing_extensions import TypedDict
from pydantic import BaseModel, ConfigDict, Field
from collections.abc import Sequence

# ========== Playlist =============

# raw data as saved in persistent storage

class PlaylistRaw(BaseModel):
  spotify_id: str
  spotify_url: str
  name: str
  enabled: bool
  lastSpotifyFetchDateTimeISO: Optional[str] = None

class TrackRaw(BaseModel):
  spotify_id: str
  title: str
  artists: str
  album: str
  release_date: str
  duration_ms: int
  preview_url: str
  youtube_url: Optional[str] = None
  cover_url: Optional[str] = None
  recording_label: Optional[str] = None
  
class UserConfig(BaseModel):
  model_config = ConfigDict(extra="ignore")
  version: int
  setting_disk_download_path: str
  setting_disk_format: str
  setting_disk_quality: str
  setting_disk_filename_pattern: str
  setting_disk_add_meta_tags: bool
  data_playlists: list[PlaylistRaw]
  data_playlists_songs: dict[str, list[TrackRaw]]

# derived data (raw + computed)

class TrackDerived(BaseModel):
  spotify_id: str
  spotify_url: str
  spotify_playlist_id: str
  spotify_preview_url: str
  spotify_duration_ms: int
  spotify_duration_mm_ss: str
  title: str
  artists: str
  album: str
  youtube_url: Optional[str] = None
  cover_url: Optional[str] = None
  recording_label: Optional[str] = None
  disk_file_name: str
  disk_file_name_without_extension: str
  disk_file_path: str
  disk_file_path_without_extension: str
  has_disk_file: bool
  disk_file_duration_ms: Optional[int] = None
  disk_file_duration_mm_ss: Optional[str] = None


class PlaylistDerived(PlaylistRaw):
  spotify_url: str
  spotify_id: str
  lastSpotifyFetchDateTimeISO: Optional[str] = None
  tracks: Sequence[TrackDerived]
  tracks_count: int
  disk_path: str

# add

class PlaylistAddPlaylistPayload(BaseModel):
  playlistSpotifyUrl: str

# edit

class PlaylistEditTrackPayload(BaseModel):
  playlist_id: str
  track_id: str
  youtube_url: Optional[str | None] = None
  
  
# ========== Settings =============
  
class SettingsReadonly(BaseModel):
  user_config_file_path: str
  
class SettingsMutable(BaseModel):
  setting_disk_download_path: str
  setting_disk_filename_pattern: str

class Settings(BaseModel):
  readonly: SettingsReadonly
  mutable: SettingsMutable

# ========== WS (websocket) =============

class FrontendQueryKeys: 
  PLAYLIST_ALL = ['playlists']
  @staticmethod
  def PLAYLIST_DETAILS(playlist_id: str): return ['playlists', playlist_id]


class WsBackendEventPayloadTypeMessage(BaseModel):
  kind: Literal["MESSAGE"] = "MESSAGE"
  text: str
  severity: Literal[
    "INFO",
    "WARNING",
    "ERROR",
    "SUCCESS",
  ] = "INFO"

class WsBackendEventPayloadTypeFrontendQueryInvalidation(BaseModel):
  kind: Literal["FRONTEND_QUERY_INVALIDATION"] = "FRONTEND_QUERY_INVALIDATION"
  queryKeys: list[str]
  
class WsBackendEventPayloadTypeJobProgressJobItem(TypedDict):
  title: str
  executionStatus: Literal[
    "WAITING_START",
    "RUNNING",
    "COMPLETED",
    "CANCELED",
    "ERRORED",
  ]
  progress: float
  stepsTotal: int
  stepsCompleted: int
  messages: list[str]
    
class WsBackendEventPayloadTypeJobProgress(BaseModel):
  kind: Literal["JOB_PROGRESS"] = "JOB_PROGRESS"
  dateTimeISO: str
  jobs: list[WsBackendEventPayloadTypeJobProgressJobItem]
  
WsBackendEventPayload = Union[
  WsBackendEventPayloadTypeMessage, 
  WsBackendEventPayloadTypeFrontendQueryInvalidation,
  WsBackendEventPayloadTypeJobProgress,
]

class WsBackendEvent(BaseModel):
  dateTimeISO: str
  payload: WsBackendEventPayload = Field(discriminator="kind")


# ========== Utils =============

class ApiRouteUtilDiskRevealInFinderPayload(BaseModel):
  path: str