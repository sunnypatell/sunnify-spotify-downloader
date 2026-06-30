import axios, { type AxiosInstance } from 'axios';
import {
  schemaWsBackendEvent,
  type WsBackendEvent,
  type DerivedPlaylist,
  type DerivedTrack,
  type PlaylistEditTrackPayload,
  type PlaylistRaw,
  type Settings,
} from './types';
import { toast } from '@/components/ui/sonner';

export class ApiClient {
  private baseUrlHttp: string;
  private baseUrlWs: string;
  private axiosInstance: AxiosInstance;

  constructor(config: {
    baseUrlHttp: string;
    baseUrlWs: string;
  }) {
    this.baseUrlHttp = config.baseUrlHttp;
    this.baseUrlWs = config.baseUrlWs;
    this.axiosInstance = axios.create({
      baseURL: this.baseUrlHttp,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Interceptor for error handling
    this.axiosInstance.interceptors.response.use(
      (response) => response,
      (error) => {
        // Handle API errors
        const resStatus = error.response?.status ?? error.response?.statusText ?? '-';
        const resMessage = error.response?.data
          ? JSON.stringify(error.response?.data)
          : (error.message ?? 'No error message');
        const logText = `API Error!\nHTTP Status: ${resStatus}\n${resMessage}`;
        console.error(logText);
        toast.error(logText);
        return Promise.reject(error);
      }
    );
  }

  // ========== Health ==========

  getHealth() {
    return this.axiosInstance
      .get('/health')
      .then((res) => res.data);
  }

  // ========== Playlists ==========

  playlist_addPlaylist({
    playlistSpotifyUrl,
  }: {
    playlistSpotifyUrl: string;
  }) {
    return this.axiosInstance
      .post<true>('/playlists/add', { playlistSpotifyUrl })
      .then((res) => res.data)
      .then((data) => {
        toast.success('Playlist added');
        return data;
      });
  }

  playlist_getAll() {
    return this.axiosInstance
      .get<PlaylistRaw[]>('/playlists/')
      .then((res) => res.data);
    // .then((data) => {
    //   toast.info('Playlists loaded');
    //   return data;
    // });
  }

  playlist_getOne({
    playlistId,
  }: {
    playlistId: DerivedPlaylist['spotify_id'];
  }) {
    return this.axiosInstance
      .get<DerivedPlaylist>(`/playlists/${playlistId}`)
      .then((res) => res.data);
    // .then((data) => {
    //   toast.info(`Playlist "${data.name}" loaded`);
    //   return data;
    // });
  }

  playlist_spotify_refetch({
    playlistId,
    playlistName,
  }: {
    playlistId: DerivedPlaylist['spotify_id'];
    playlistName: DerivedPlaylist['name'];
  }) {
    return this.axiosInstance
      .post<boolean>(`/playlists/${playlistId}/spotify/refetch`)
      .then((res) => res.data)
      .then((data) => {
        toast.success(`Playlist "${playlistName}" (${playlistId}) updated - Spotify`);
        return data;
      });
  }

  playlist_updateTrack(payload: PlaylistEditTrackPayload) {
    return this.axiosInstance
      .post<void>(`/playlists/edit-track`, payload)
      .then((res) => res.data)
      .then((data) => {
        toast.success('Track updated');
        return data;
      });
  }

  playlist_youtube_autoSearchUrlSingleTrack({
    playlistId,
    trackId
  }: {
    playlistId: DerivedPlaylist['spotify_id'];
    trackId: DerivedTrack['spotify_id'];
  }) {
    return this.axiosInstance
      .post<true>(`/playlists/${playlistId}/track/${trackId}/youtube/auto-search-url`)
      .then((res) => res.data)
      .then((data) => {
        toast.success('Track updated');
        return data;
      });
  }

  playlist_youtube_autoSearchUrlAllTracks({
    playlistId,
  }: {
    playlistId: DerivedPlaylist['spotify_id'];
  }) {
    return this.axiosInstance
      .post<true>(`/playlists/${playlistId}/youtube/auto-search-url`)
      .then((res) => res.data);
  }

  playlist_disk_getAudioFile({
    playlistId,
    trackId
  }: {
    playlistId: DerivedPlaylist['spotify_id'];
    trackId: DerivedTrack['spotify_id'];
  }) {
    return this.axiosInstance
      .post<File>(this.playlist_disk_getAudioFile_BUILD_URL({ playlistId, trackId }))
      .then((res) => res.data)
      .then((data) => {
        toast.success('Track updated');
        return data;
      });
  }

  playlist_disk_getAudioFile_BUILD_URL({
    playlistId,
    trackId
  }: {
    playlistId: DerivedPlaylist['spotify_id'];
    trackId: DerivedTrack['spotify_id'];
  }) {
    const path = `/playlists/${playlistId}/track/${trackId}/disk/get-audio-file`;
    return this.baseUrlHttp + path;
  }

  playlist_disk_deleteFile({
    playlistId,
    trackId
  }: {
    playlistId: DerivedPlaylist['spotify_id'];
    trackId: DerivedTrack['spotify_id'];
  }) {
    return this.axiosInstance
      .post<boolean>(`/playlists/${playlistId}/track/${trackId}/disk/delete-file`)
      .then((res) => res.data)
      .then((data) => {
        toast.success('Track deleted');
        return data;
      });
  }

  playlist_disk_downloadSingleTrack({
    playlistId,
    trackId
  }: {
    playlistId: DerivedPlaylist['spotify_id'];
    trackId: DerivedTrack['spotify_id'];
  }) {
    const loadingToast = toast.loading('Downloading track...');
    return this.axiosInstance
      .post<true>(`/playlists/${playlistId}/track/${trackId}/disk/download`)
      .then((res) => res.data)
      .then((data) => {
        toast.dismiss(loadingToast);
        toast.success('Track downloaded');
        return data;
      })
      .catch((error) => {
        toast.dismiss(loadingToast);
        return Promise.reject(error);
      });
  }

  playlist_disk_downloadAllTracks({
    playlistId,
  }: {
    playlistId: DerivedPlaylist['spotify_id'];
  }) {
    return this.axiosInstance
      .post<true>(`/playlists/${playlistId}/disk/download-all/job/start`)
      .then((res) => res.data);
  }


  // ========== Settings ==========

  settings_get() {
    return this.axiosInstance
      .get<Settings>(`/settings`)
      .then((res) => res.data);
  }

  settings_update(payload: Settings['mutable']) {
    return this.axiosInstance
      .put<boolean>(`/settings`, payload)
      .then((res) => res.data);
  }

  // ========== WS (websocket) ==========

  wsEntryPointConnect() {
    return {
      getWs: () => new WebSocket(`${this.baseUrlWs}/ws/entry-point`),
      _responseDataSchema: schemaWsBackendEvent,
      _responseDataType: {} as WsBackendEvent
    };
  }

  // ========== Demo ==========

  demo_jobDemoStart() {
    return this.axiosInstance
      .post<true>('/demo/job-demo/start')
      .then((res) => res.data);
  }

  // ========== Utils ==========

  utils_disk_revealInFinder(payload: {
    path: string;
  }) {
    return this.axiosInstance
      .post<true>('/utils/disk/reveal-in-finder', payload)
      .then((res) => res.data);
  }



}
