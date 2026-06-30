from urllib.parse import urlparse
from core.classes.music_providers.utils_spotify_fetcher_api import SpotifyFetcherApi


class UtilsSpotify:
  @staticmethod
  def deriveSpotifyPlaylistIdFromUrl(spotifyPlaylistUrl: str) -> str:
    # input: https://open.spotify.com/playlist/6anvql1OK0kBbmX5tyFWYz?si=dauxr8iKRGu9LVClCqi9xg
    # output: 6anvql1OK0kBbmX5tyFWYz
    id = urlparse(spotifyPlaylistUrl).path.split("/")[2]
    return id
  
  @staticmethod
  def deriveSpotifyPlaylistUrlFromId(spotifyPlaylistId: str) -> str:
    return f"https://open.spotify.com/playlist/{spotifyPlaylistId}"
  
  @staticmethod
  def deriveSpotifyTrackUrlFromId(spotifyTrackId: str) -> str:
    return f"https://open.spotify.com/track/{spotifyTrackId}"
  
  @staticmethod
  def fetchSpotifyPlaylistMetadata(spotifyPlaylistId: str):
    spotifyApi = SpotifyFetcherApi()
    
    playlistExistsInSpotify = spotifyApi.validate_playlist(spotifyPlaylistId)
    if not playlistExistsInSpotify:
      return None
    
    playlistMetadata = spotifyApi.get_playlist_metadata(spotifyPlaylistId)
    return playlistMetadata
  
  @staticmethod
  def fetchSpotifyPlaylistTracksAndData(spotifyPlaylistId: str): 
    """Fetch playlist data from Spotify's embed page.

    The embed page (https://open.spotify.com/embed/playlist/{id}) contains
    full track data in a __NEXT_DATA__ JSON blob, including:
    - Track titles, artists, durations
    - Track URIs/IDs
    - 96kbps audio preview URLs
    - Anonymous access tokens (can be used with spclient API)

    This works without any authentication.
    Limitation: Returns max ~100 tracks per playlist.
    """
    spotifyApi = SpotifyFetcherApi()
    
    playlistExistsInSpotify = spotifyApi.validate_playlist(spotifyPlaylistId)
    if not playlistExistsInSpotify:
      return None
    
    playlistMetadata = spotifyApi.get_playlist_metadata(spotifyPlaylistId)
    playlistTracks = [
      spotifyApi.get_track(track_id=track.id)
      for track in list(spotifyApi.iter_playlist_tracks(spotifyPlaylistId))
    ]
    return playlistMetadata, playlistTracks
    
  