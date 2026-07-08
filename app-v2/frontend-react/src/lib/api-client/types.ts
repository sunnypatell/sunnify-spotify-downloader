import { z } from 'zod';

// ========= Playlist =========

// main types

export interface PlaylistRaw {
  spotify_id: string,
  spotify_url: string,
  name: string,
  enabled: boolean,
  lastSpotifyFetchDateTimeISO?: string,
}

export interface DerivedTrack {
  spotify_id: string,
  spotify_url: string,
  spotify_playlist_id: string,
  spotify_preview_url: string,
  spotify_duration_ms: number,
  spotify_duration_mm_ss: string,
  title: string,
  artists: string,
  album: string,
  youtube_url?: string,
  cover_url?: string,
  recording_label?: string,
  disk_file_name: string,
  disk_file_name_without_extension: string,
  disk_file_path: string,
  disk_file_path_without_extension: string,
  has_disk_file: boolean,
  disk_file_duration_ms?: number | null,
  disk_file_duration_mm_ss?: string | null,
}

export interface DerivedPlaylist {
  spotify_id: string,
  spotify_url: string,
  name: string,
  enabled: boolean,
  lastSpotifyFetchDateTimeISO?: string,
  tracks: DerivedTrack[],
  tracks_count: number,
  disk_path: string,
}

// edit types

export interface PlaylistEditTrackPayload {
  playlist_id: string,
  track_id: string,
  youtube_url?: string | null;
}


// ========= WS =========

export const schemaWsBackendEvent = z.object({
  /** DateTime in ISO format of when the event was triggered by the backend */
  dateTimeISO: z.string(),
  payload: z.discriminatedUnion('kind', [
    z.object({
      kind: z.literal('MESSAGE'),
      text: z.string(),
      severity: z.enum([
        'INFO',
        'WARNING',
        'ERROR',
        'SUCCESS',
      ]),
    }),
    z.object({
      kind: z.literal('FRONTEND_QUERY_INVALIDATION'),
      /** Query Keys to invalidate in react-query QueryClient */
      queryKeys: z.array(z.string()),
    }),
    z.object({
      kind: z.literal('JOB_PROGRESS'),
      /** DateTime in ISO format of when the event was triggered by the backend */
      dateTimeISO: z.string(),
      jobs: z.array(z.object({
        title: z.string(),
        executionStatus: z.enum([
          'WAITING_START',
          'RUNNING',
          'COMPLETED',
          'CANCELED',
          "ERRORED",
        ]),
        progress: z.number(),
        stepsTotal: z.number(),
        stepsCompleted: z.number(),
        messages: z.array(z.string()),
      }))
    }),
  ])
});

export type WsBackendEvent = z.infer<typeof schemaWsBackendEvent>;



// ========= Settings =========

export const schemaSettings = z.object({
  readonly: z.object({
    user_config_file_path: z.string(),
    binary_deno_file_path: z.string(),
    binary_ffmpeg_file_path: z.string(),
  }),
  mutable: z.object({
    setting_disk_download_path: z.string().min(1),
    setting_disk_filename_pattern: z.string().min(1),
  }),
});

export type Settings = z.infer<typeof schemaSettings>;
