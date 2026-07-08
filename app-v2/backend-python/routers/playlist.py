from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from models.new import (
  PlaylistRaw, 
  TrackRaw, 
  PlaylistDerived, 
  PlaylistAddPlaylistPayload, 
  PlaylistEditTrackPayload, 
  WsBackendEventPayloadTypeMessage,
)
from core.singleton.logger import logger
from core.singleton.user_config_api import userConfigReaderApi, userConfigApi
from core.singleton.jobs_executor import jobsExecutor
from core.singleton.websocket_event_emitter import webSocketEventEmitter
from core.classes.data.data_layer_mapper import DataLayerMapper
from core.classes.operations.utils_operations import UtilsOperations
from core.classes.music_providers.utils_spotify import UtilsSpotify
from core.classes.music_providers.utils_youtube_fetcher_api import UtilsYoutubeFetcherApi
from core.classes.music_providers.utils_track_disk import UtilsTrackDisk
from core.classes.utils.utils_time import UtilsTime, UtilsTimeExecutionTimer

router = APIRouter(prefix="/playlists", tags=["playlists"])

# ============================================================================
# Playlists endpoints
# ============================================================================


@router.get("/", response_model=list[PlaylistRaw])
async def playlists_getAll():
  """List all saved playlists from config"""
  logger.info("Fetching playlists list...")
  # get from db
  timerGetDb = UtilsTimeExecutionTimer()
  
  playlistsRaw = userConfigReaderApi.getPlaylistsRaw()
  
  timeGetDb = timerGetDb.end()
  logger.info(f"Got {len(playlistsRaw)} raw playlists from DB! Read Time: {timeGetDb}!")
  return playlistsRaw

@router.post("/add", response_model=bool)
async def playlist_addOne(request: PlaylistAddPlaylistPayload):
  # derive playlist spotify id
  playlistId = UtilsSpotify.deriveSpotifyPlaylistIdFromUrl(request.playlistSpotifyUrl)
  playlistUrl = UtilsSpotify.deriveSpotifyPlaylistUrlFromId(playlistId)
  
  # get playlist data from spotify
  freshPlaylistSpotifyData = UtilsSpotify.fetchSpotifyPlaylistMetadata(spotifyPlaylistId=playlistId)
  if not freshPlaylistSpotifyData:
    logger.error(f"Playlist {playlistId} not found in Spotify")
    raise HTTPException(status_code=404, detail="Playlist not found in Spotify. Maybe you made the playlist private or deleted it from Spotify?")
  
  # create new raw data (for user config)
  addedResult = userConfigReaderApi.addPlaylist(
    add_payload=PlaylistRaw(
      spotify_id=playlistId,
      spotify_url=playlistUrl,
      name=freshPlaylistSpotifyData.name,
      enabled=True,
      lastSpotifyFetchDateTimeISO=None
    )
  )
  
  if addedResult[0] == False:
    logger.error(f"Error adding playlist {playlistId} to user config: {addedResult[1]}")
    raise HTTPException(status_code=500, detail=addedResult[1])
  
  return True


@router.get("/{playlist_id}", response_model=PlaylistDerived)
async def playlist_getOne(playlist_id: str):
  """Get single playlist with all songs"""
  # find playlist by id
  timerGetDb = UtilsTimeExecutionTimer()
  
  playlistRaw = userConfigReaderApi.getPlaylistRaw(
    playlist_id=playlist_id, 
  )
  timeGetDb = timerGetDb.end()
  
  if not playlistRaw:
    logger.error(f"Playlist {playlist_id} not found. Read time: {timeGetDb}")
    raise HTTPException(status_code=404, detail="Playlist not found")
  
  # derive PlaylistDerived
  timerDerive = UtilsTimeExecutionTimer()
  
  playlistDerived = await DataLayerMapper.mapPlaylistRawToPlaylistDerived_ASYNC(
    userConfigApi=userConfigApi,
    playlistRaw=playlistRaw, 
  )
  
  timeDerive = timerDerive.end()
  logger.info(f"Playlist {playlist_id} derived! Read time: {timeGetDb} | Derive time: {timeDerive}")
  
  return playlistDerived
  
@router.post("/{playlist_id}/spotify/refetch", response_model=bool)
async def playlist_spotify_refetchPlaylist(playlist_id: str):
  """Fetch fresh data from Spotify and merge with local config"""
  logger.info(f"Refreshing playlist {playlist_id}")
  
  # 1. ensure playlist exists in user config
  oldPlaylistRaw = userConfigReaderApi.getPlaylistRaw(
    playlist_id=playlist_id,
  )
  if not oldPlaylistRaw:
    logger.error(f"Playlist {playlist_id} not found in your config")
    raise HTTPException(status_code=404, detail="Playlist not found in your config")
  
  # 2. fetch updated playlist data from Spotify
  freshPlaylistSpotifyData = UtilsSpotify.fetchSpotifyPlaylistTracksAndData(
    spotifyPlaylistId=playlist_id
  )
  if not freshPlaylistSpotifyData:
    logger.error(f"Playlist {playlist_id} not found in Spotify")
    raise HTTPException(status_code=404, detail="Playlist not found in Spotify but is in your config. Maybe you made the playlist private or deleted it from Spotify?")
  freshSpotifyPlaylistTracks = freshPlaylistSpotifyData[1]
  # print(freshSpotifyPlaylistMeta)
  # print(freshSpotifyPlaylistTracks[0])
  
  # 3. derive PlaylistDerived
  oldPlaylistDerived = await DataLayerMapper.mapPlaylistRawToPlaylistDerived_ASYNC(
    userConfigApi=userConfigApi,
    playlistRaw=oldPlaylistRaw,
  )
  
  # 4. create new TrackRaw data (for saving to user config) 
  newConfigTracks: list[TrackRaw] = []
  for freshSpotifyTrack in freshSpotifyPlaylistTracks:  
    # get exiing track for this id    
    oldTrackInConfigData = userConfigReaderApi.getTrackRaw(
      playlist_id=playlist_id, 
      track_id=freshSpotifyTrack.spotify_id, 
    )
    oldTrackInConfig = oldTrackInConfigData[0] if oldTrackInConfigData else None
    # create a nww TrackRaw item
    newConfigTrack = TrackRaw(
      spotify_id=freshSpotifyTrack.spotify_id,
      title=freshSpotifyTrack.title,
      artists=freshSpotifyTrack.artists,
      album=freshSpotifyTrack.album or "",
      release_date=freshSpotifyTrack.release_date or "",
      duration_ms=freshSpotifyTrack.duration_ms or 0,
      preview_url=freshSpotifyTrack.preview_url or "",
      youtube_url=oldTrackInConfig.youtube_url if oldTrackInConfig else None,
      cover_url=freshSpotifyTrack.cover_url,
      recording_label=freshSpotifyTrack.recording_label,
    )
    newConfigTracks.append(newConfigTrack)
    # logger.info(f"newConfigTrack: {newConfigTrack}")
  
  # 5. update/save tracks to user config
  # logger.info(f"json: {newConfigTracks}")
  userConfigReaderApi.updatePlaylistTracks(
    playlist_id=playlist_id,
    newTracksRaw=newConfigTracks,
  )
  userConfigReaderApi.updatePlaylist(
    update_payload=PlaylistRaw(
      spotify_id=oldPlaylistRaw.spotify_id,
      spotify_url=oldPlaylistRaw.spotify_url,
      name=oldPlaylistRaw.name,
      enabled=oldPlaylistRaw.enabled,
      lastSpotifyFetchDateTimeISO=UtilsTime.getCurrentDateTimeIso(),
    )
  )
  
  # 6. derive changes
  oldTracksIds = set([track.spotify_id for track in oldPlaylistDerived.tracks])
  newTracksIds = set([track.spotify_id for track in newConfigTracks])
  addedTracksIds = newTracksIds - oldTracksIds
  deletedTracksIds = oldTracksIds - newTracksIds
  
  # 7. notify new tracks
  playlistName = oldPlaylistDerived.name
  oldTracksCount = len(oldTracksIds)
  newTracksCount = len(newTracksIds)
  addedTracksCount = len(addedTracksIds)
  deletedTracksCount = len(deletedTracksIds)
  await webSocketEventEmitter.emit(
    eventPayload=WsBackendEventPayloadTypeMessage(
      text=f"Playlist \"{playlistName}\" updated!\nTrack count: {oldTracksCount} -> {newTracksCount}.\nAdded tracks: {addedTracksCount}\nDeleted tracks: {deletedTracksCount}",
      severity="SUCCESS"
    )
  )
  
  # 8. reply to client
  return True

@router.post("/edit-track")
async def playlist_editTrack(request: PlaylistEditTrackPayload):
  """Edit track in user config"""
  logger.info(f"Editing track {request.track_id} of playlist {request.playlist_id}, request: {request}")
  
  # update
  result = userConfigReaderApi.updatePlaylistTrack(
    update_payload=request
  )
  
  # if track not found, 404
  if result == None or result != True:
    logger.error(f"Track {request.track_id} not found in playlist {request.playlist_id}")
    raise HTTPException(status_code=404, detail="Track not found")
  
  return True
    
@router.post("/{playlist_id}/track/{track_id}/youtube/auto-search-url", response_model=bool)
async def playlist_youtube_autoSearchUrl_singleTrack(playlist_id: str, track_id: str):
  """Find and set YouTube URL for a track"""
  logger.info(f"Find YouTube URL for track {track_id}")
  
  # get track
  trackRawData = userConfigReaderApi.getTrackRaw(
    playlist_id=playlist_id,
    track_id=track_id,
  )
  if not trackRawData:
    logger.error(f"Track {track_id} not found in playlist {playlist_id}")
    raise HTTPException(status_code=404, detail="Track not found")
  
  # derive track derived
  trackRaw, playlistRaw, trackRawIndex = trackRawData
  trackDerived = DataLayerMapper.mapTrackRawToTrackDerived(
    userConfigApi=userConfigApi,
    trackRaw=trackRaw,
    playlistRaw=playlistRaw,
    index=trackRawIndex,
  )
  
  # find YouTube URL
  youtubeUrl = UtilsYoutubeFetcherApi.findYoutubeUrlOfTrack(trackDerived=trackDerived)
  logger.info(f"Found YouTube URL: {youtubeUrl}")
  if not youtubeUrl:
    logger.error(f"Could not find YouTube URL for track {track_id}")
    raise HTTPException(status_code=500, detail="Could not find YouTube URL")
  
  # update track in config
  updateResult = userConfigReaderApi.updatePlaylistTrack(
    update_payload=PlaylistEditTrackPayload(
      playlist_id=playlist_id,
      track_id=track_id,
      youtube_url=youtubeUrl
    )
  )
  if updateResult != True:
    logger.error(f"Could not update Track {track_id} in playlist {playlist_id}")
    raise HTTPException(status_code=500, detail="Cannot update track")
  
  return updateResult

@router.post("/{playlist_id}/youtube/auto-search-url", response_model=bool)
async def playlist_youtube_autoSearchUrl_allTracks(playlist_id: str):
  """Find and set YouTube URL for all tracks of a playlist that have no YouTube URL"""
  logger.info(f"Find YouTube URL for all tracks of playlist {playlist_id}")
  
  # get playlist
  playlistRaw = userConfigReaderApi.getPlaylistRaw(
    playlist_id=playlist_id,
  )
  if not playlistRaw:
    logger.error(f"Playlist {playlist_id} not found in user config")
    raise HTTPException(status_code=404, detail="Playlist not found")
  
  # derive playlist derived
  playlistDerived = await DataLayerMapper.mapPlaylistRawToPlaylistDerived_ASYNC(
    userConfigApi=userConfigApi,
    playlistRaw=playlistRaw,
  )
  
  # crate job (find YouTube URLs) + schedule
  job = UtilsOperations.doYoutubeAutoSarchUrlOnAllPlaylistTracks(playlistDerived)
  jobsExecutor.setAndStartNewJob(job)
  
  return True

@router.get("/{playlist_id}/track/{track_id}/disk/get-audio-file", response_class=FileResponse)
async def playlist_disk_getAudioFile(playlist_id: str, track_id: str):
  """Play track file from disk"""
  logger.info(f"Play request for track {track_id}")
  
  # get track raw
  trackRawData = userConfigReaderApi.getTrackRaw(
    playlist_id=playlist_id,
    track_id=track_id,
  )
  if not trackRawData:
    logger.error(f"Track {track_id} not found in playlist {playlist_id}")
    raise HTTPException(status_code=404, detail="Track not found")
  trackRaw, playlistRaw, trackRawIndex = trackRawData
  
  # derive track derived
  trackDerived = DataLayerMapper.mapTrackRawToTrackDerived(
    userConfigApi=userConfigApi,
    trackRaw=trackRaw,
    playlistRaw=playlistRaw,
    index=trackRawIndex,
  )
  
  # return file
  return FileResponse(
    path=trackDerived.disk_file_path,
    media_type="audio/mpeg",
    filename="song.mp3",
  )
    
@router.post("/{playlist_id}/track/{track_id}/disk/download", response_model=bool)
async def playlist_disk_download_singleTrack(playlist_id: str, track_id: str):
  """Download track from YouTube as MP3 and save to disk"""
  logger.info(f"Downloading track {track_id}")
  
  # get track raw
  trackRawData = userConfigReaderApi.getTrackRaw(
    playlist_id=playlist_id,
    track_id=track_id,
  )
  if not trackRawData:
    logger.error(f"Track {track_id} not found in playlist {playlist_id}")
    raise HTTPException(status_code=404, detail="Track not found")
  trackRaw, playlistRaw, trackRawIndex = trackRawData
  
  # derive track derived
  trackDerived = DataLayerMapper.mapTrackRawToTrackDerived(
    userConfigApi=userConfigApi,
    trackRaw=trackRaw,
    playlistRaw=playlistRaw,
    index=trackRawIndex,
  )
  
  # download track
  downloadResult = await UtilsOperations.downloadSingleTrack(trackDerived)
  
  if downloadResult[0] == False and downloadResult[1] == "FFMPEG_NOT_INSTALLED":
    logger.error(f"FFmpeg not installed (Known error)")
    raise HTTPException(status_code=500, detail="Could not download track because FFMPEG is not installed in your system")
  
  if downloadResult[0] == False and downloadResult[1] == "NO_YOUTUBE_URL":
    logger.error(f"Could not find YouTube URL for track {track_id} (Known error)")
    raise HTTPException(status_code=500, detail="Could not find YouTube URL")
  
  if downloadResult[0] == False and downloadResult[1] == "DISK_PATH_NOT_ACCESSIBLE":
    logger.error(f"Could not write to disk folder for track {track_id} (Known error)")
    raise HTTPException(status_code=500, detail="Write to disk failed. The directory is not accessible!")
  
  if downloadResult[0] == False and downloadResult[1] == "ERROR_DOWNLOADING":
    logger.error(f"Could not download track {track_id} (Known error)")
    logger.error(downloadResult[2])
    raise HTTPException(status_code=500, detail="Could not download track")
  
  if downloadResult[0] != True:
    logger.error(f"Could not download track {track_id} (Unknown error)")
    raise HTTPException(status_code=500, detail="Could not download track (Unknown error)")
  
  return True
  
@router.post("/{playlist_id}/track/{track_id}/disk/delete-file", response_model=bool)
async def playlist_disk_deleteTrackFile(playlist_id: str, track_id: str):
  """Delete track file from disk"""
  logger.info(f"Delete request for track {track_id}")
  
  # get track raw
  trackRawData = userConfigReaderApi.getTrackRaw(
    playlist_id=playlist_id,
    track_id=track_id,
  )
  if not trackRawData:
    logger.error(f"Track {track_id} not found in playlist {playlist_id}")
    raise HTTPException(status_code=404, detail="Track not found")
  trackRaw, playlistRaw, trackRawIndex = trackRawData
  
  # derive track derived
  trackDerived = DataLayerMapper.mapTrackRawToTrackDerived(
    userConfigApi=userConfigApi,
    trackRaw=trackRaw,
    playlistRaw=playlistRaw,
    index=trackRawIndex,
  )
  
  # delete file
  deletedResult = UtilsTrackDisk.deleteTrackFile(trackDerived)
  
  if deletedResult == "FILE_NOT_FOUND":
    logger.error(f"Track {track_id} not found in playlist {playlist_id}")
    raise HTTPException(status_code=404, detail="File not found in disk")
  
  if deletedResult == "FILE_DELETE_ERROR":
    logger.error(f"Error deleting track {track_id} from playlist {playlist_id}")
    raise HTTPException(status_code=500, detail="Error deleting file from disk")
  
  return True
  
@router.post("/{playlist_id}/disk/download-all/job/start", response_model=bool)
async def playlist_disk_download_allTracks(playlist_id: str):
  """Start download of all missing tracks of the playlist"""
  # get playlist raw
  playlistRaw = userConfigReaderApi.getPlaylistRaw(
    playlist_id=playlist_id,
  )
  if not playlistRaw:
    logger.error(f"Playlist {playlist_id} not found")
    raise HTTPException(status_code=404, detail="Playlist not found")
  # derive playlist derived
  playlistDerived = await DataLayerMapper.mapPlaylistRawToPlaylistDerived_ASYNC(
    userConfigApi=userConfigApi,
    playlistRaw=playlistRaw,
  )
  # create job
  job = UtilsOperations.downloadPlaylistAllMissingTrack(
    playlistDerived=playlistDerived
  )
  # schedule job
  jobsExecutor.setAndStartNewJob(job)
  # reply
  return True
  
  