import asyncio
from models.new import (
  PlaylistDerived, 
  TrackDerived,
  PlaylistEditTrackPayload, 
  WsBackendEventPayloadTypeMessage,
  WsBackendEventPayloadTypeFrontendQueryInvalidation,
  FrontendQueryKeys
)
from core.singleton.logger import logger
from core.singleton.user_config_api import userConfigApi, userConfigReaderApi
from core.singleton.websocket_event_emitter import webSocketEventEmitter
from core.classes.jobs.job import Job
from core.classes.music_providers.utils_youtube_fetcher_api import UtilsYoutubeFetcherApi
from core.classes.music_providers.utils_metadata_writer import write_metadata_to_file
from core.classes.utils.utils_time import UtilsTimeExecutionTimer


class UtilsOperations:
  """High Level API for playlist and tracks operations"""
  @staticmethod
  async def downloadSingleTrack(trackDerived: TrackDerived):
    """Download single track and optionally embed metadata."""
    
    # sub-fns
    async def downloadFile(trackDerived: TrackDerived):
      maxRetries = 5
      retryCount = 0
      execTimer = UtilsTimeExecutionTimer()
      while (retryCount < maxRetries):
        retryCount += 1
        # download
        output = await asyncio.to_thread(
          UtilsYoutubeFetcherApi.downloadYoutubeTrackAsMp3,
          trackDerived=trackDerived
        )
        # if success -> return
        if output[0]:
          executionTime = execTimer.end()
          await webSocketEventEmitter.emit(
            eventPayload=WsBackendEventPayloadTypeMessage(text=f"Attempt {retryCount}/{maxRetries} to download track. Success! Duration: {executionTime}")
          )
          return output
        # if failed -> retry
        await webSocketEventEmitter.emit(
          eventPayload=WsBackendEventPayloadTypeMessage(text=f"Attempt {retryCount}/{maxRetries} to download track. Failed {output[1]}. Retrying...")
        )
      # if failed after max retries
      executionTime = execTimer.end()
      await webSocketEventEmitter.emit(
        eventPayload=WsBackendEventPayloadTypeMessage(text=f"Failed to download track after {maxRetries} attempts. Duration: {executionTime}")
      )
      return (False, "MAX_RETRIES_EXCEEDED")
    
    async def addMetadataToFile(trackDerived: TrackDerived):
      maxRetries = 5
      retryCount = 0
      execTimer = UtilsTimeExecutionTimer()
      while (retryCount < maxRetries):
        retryCount += 1
        # embed
        output = await write_metadata_to_file(
          file_path=trackDerived.disk_file_path,
          track_data=trackDerived,
        )
        # if success -> return
        if output[0]:
          executionTime = execTimer.end()
          await webSocketEventEmitter.emit(
            eventPayload=WsBackendEventPayloadTypeMessage(text=f"Attempt {retryCount}/{maxRetries} to embed metadata. Success! Duration: {executionTime}")
          )
          return output
        # if failed -> retry
        await webSocketEventEmitter.emit(
          eventPayload=WsBackendEventPayloadTypeMessage(text=f"Attempt {retryCount}/{maxRetries} to embed metadata. Failed. {output[1]}. Retrying...")
        )
      # if failed after max retries
      executionTime = execTimer.end()
      await webSocketEventEmitter.emit(
        eventPayload=WsBackendEventPayloadTypeMessage(text=f"Failed to embed metadata after {maxRetries} attempts. Duration: {executionTime}")
      )
      return (False, "MAX_RETRIES_EXCEEDED")
    
    # 1. sleep
    await asyncio.sleep(2)

    # 2. Download track with retry
    logger.info(f"Downloading track {trackDerived.artists} - {trackDerived.title}")
    download_result = await downloadFile(trackDerived=trackDerived)
    if not download_result[0]:
      logger.warning(f"Downloading track {trackDerived.artists} - {trackDerived.title} ❌ FAILED: {download_result[1]}")
      return download_result

    # 3. Embed metadata if enabled
    if userConfigApi.config_as_object.setting_disk_add_meta_tags:
      logger.info(f"Embedding metadata for track {trackDerived.artists} - {trackDerived.title}")
      metadata_result = await addMetadataToFile(trackDerived=trackDerived)
      if not metadata_result[0]:
        logger.warning(f"Embedding metadata for track {trackDerived.artists} - {trackDerived.title} ❌ FAILED: {metadata_result[1]}")
        return metadata_result

    return (True, "SUCCESS")
  
  @staticmethod
  def downloadPlaylistAllMissingTrack(playlistDerived: PlaylistDerived):
    # define job input
    playlistId = playlistDerived.spotify_id
    tracksDerived = playlistDerived.model_copy(deep=True).tracks
    trackCount = len(tracksDerived)
    jobStepCount = trackCount
    
    # crate job fn
    async def jobFn(job: Job):
      # constants
      delayBetweenTracks = 0.05
      
      # for each track
      for trackIndex, track in enumerate(tracksDerived):
        trackNum = trackIndex + 1
        trackNumLogMsg = f"Track {trackNum}/{trackCount}"
        
        await asyncio.sleep(delayBetweenTracks)
        
        # if not must be downloaded -> skip
        hasYoutubeUrl = bool(track.youtube_url)
        hasDiskFile = bool(track.has_disk_file)
        if hasYoutubeUrl and hasDiskFile:
          await job.incrementStepCompleted()
          await job.captureMessage(kind="INFO",message=f"{trackNumLogMsg} - Skip (already downloaded)")
          await webSocketEventEmitter.emit(
            eventPayload=WsBackendEventPayloadTypeMessage(text=f"{trackNumLogMsg} - Skip (already downloaded)")
          )
          continue
        
        if not hasYoutubeUrl:
          await job.incrementStepCompleted()
          await job.captureMessage(kind="INFO",message=f"{trackNumLogMsg} - Skip (no YouTube URL)")
          await webSocketEventEmitter.emit(
            eventPayload=WsBackendEventPayloadTypeMessage(text=f"{trackNumLogMsg} - Skip (no YouTube URL)")
          )
          continue
        
        # if must be downloaded -> download
        await webSocketEventEmitter.emit(
          eventPayload=WsBackendEventPayloadTypeMessage(text=f"{trackNumLogMsg} - Downloading...")
        )
        downloadResult = await UtilsOperations.downloadSingleTrack(trackDerived=track)
        
        # - if error -> signal error but continue job
        if (not downloadResult[0]):
          await job.captureMessage(kind="ERROR",message=f"{trackNumLogMsg} - Downloading ❌ FAILED: {downloadResult[1]}")
        # - if success -> notify frontend
        else:
          await job.captureMessage(kind="INFO",message=f"{trackNumLogMsg} - Downloading ✅ SUCCESS")
          await webSocketEventEmitter.emit(
            eventPayload=WsBackendEventPayloadTypeMessage(text=f"{trackNumLogMsg} - Downloading ✅ SUCCESS")
          )
          
        # mark step as done
        await job.incrementStepCompleted()
        
        # notify frontend to invalidate playlist details
        await webSocketEventEmitter.emit(
          eventPayload=WsBackendEventPayloadTypeFrontendQueryInvalidation(
            queryKeys=FrontendQueryKeys.PLAYLIST_DETAILS(playlistId)
          )
        )
        
      # after all track handled -> notify frontend to invalidate playlist details
      await webSocketEventEmitter.emit(
        eventPayload=WsBackendEventPayloadTypeFrontendQueryInvalidation(
          queryKeys=FrontendQueryKeys.PLAYLIST_DETAILS(playlistId)
        )
      )

    # create job
    job = Job(
      title=f"Download Playlist: {playlistDerived.name}",
      totalStepCount=jobStepCount,
      jobFn=jobFn
    )
    return job
  
  @staticmethod
  def doYoutubeAutoSarchUrlOnAllPlaylistTracks(playlistDerived: PlaylistDerived):
    
    # sub-fns
    async def findYoutubeUrlOfTrack(trackDerived: TrackDerived):
      maxRetries = 5
      retryCount = 0
      while (retryCount < maxRetries):
        output = await asyncio.to_thread(
          UtilsYoutubeFetcherApi.findYoutubeUrlOfTrack,
          trackDerived=trackDerived
        )
        if output:
          return output
      return None
    
    # 1. get data
    playlistId = playlistDerived.spotify_id
    tracksCount = len(playlistDerived.tracks)
    
    # 2. define job fn
    async def jobFn(job: Job):
      for trackIndex, track in enumerate(playlistDerived.tracks):
        
        # 1. get status
        mustBeFetched = not track.youtube_url
        
        # - if youtube is already set -> skip
        if not mustBeFetched:
          await webSocketEventEmitter.emit(
            eventPayload=WsBackendEventPayloadTypeMessage(text=f"Track {trackIndex+1}/{tracksCount} - Skip (YouTube URL exists)")
          )
          await job.incrementStepCompleted()
          continue
        
        # 2. fetch
        await webSocketEventEmitter.emit(
          eventPayload=WsBackendEventPayloadTypeMessage(text=f"Track {trackIndex+1}/{tracksCount} - Searching Youtube URL...")
        )
        # - find YouTube URL
        youtubeUrl = await findYoutubeUrlOfTrack(trackDerived=track)
        # - if not found -> go next
        if not youtubeUrl:
          await webSocketEventEmitter.emit(
            eventPayload=WsBackendEventPayloadTypeMessage(text=f"Track {trackIndex+1}/{tracksCount} - Searching YouTube URL ❌ FAILED")
          )
          await job.incrementStepCompleted()
          continue
        
        # 3. update track in config
        await webSocketEventEmitter.emit(
          eventPayload=WsBackendEventPayloadTypeMessage(text=f"Track {trackIndex+1}/{tracksCount} - Searching YouTube URL ✅ SUCCESS")
        )
        await webSocketEventEmitter.emit(
          eventPayload=WsBackendEventPayloadTypeMessage(text=f"Track {trackIndex+1}/{tracksCount} - Updating YouTube URL...")
        )
        updateResult = userConfigReaderApi.updatePlaylistTrack(
          update_payload=PlaylistEditTrackPayload(
            playlist_id=playlistDerived.spotify_id,
            track_id=track.spotify_id,
            youtube_url=youtubeUrl
          )
        )
        # - if update failed
        if not updateResult:
          await webSocketEventEmitter.emit(
            eventPayload=WsBackendEventPayloadTypeMessage(text=f"Track {trackIndex+1}/{tracksCount} - Updating YouTube URL ❌ FAILED")
          )
          await job.incrementStepCompleted()
          continue
        
        await webSocketEventEmitter.emit(
          eventPayload=WsBackendEventPayloadTypeMessage(text=f"Track {trackIndex+1}/{tracksCount} - Updating YouTube URL ✅ SUCCESS")
        )
            
        # 4. mark step as completed
        await job.incrementStepCompleted()
        
        # 5. notify frontend to invalidate playlist details
        await webSocketEventEmitter.emit(
          eventPayload=WsBackendEventPayloadTypeFrontendQueryInvalidation(
            queryKeys=FrontendQueryKeys.PLAYLIST_DETAILS(playlistId)
          )
        )
    
    # 3. create job
    job = Job(
      title="Find YouTube URL for all tracks of playlist",
      totalStepCount=tracksCount,
      jobFn=jobFn
    )
    
    return job