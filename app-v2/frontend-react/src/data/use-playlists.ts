import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '#/lib/api-client/client.singleton';

const queryKeys = {
  query: {
    playlistList: ['playlists'],
    playlistDetails: (playlistId: string) => ['playlists', playlistId],
  },
  mutation: {
    addPlaylist: ['playlists', 'mutation', 'add'],
    spotifyRefetchPlaylist: ['playlists', 'mutation', 'spotify', 'refetch'],
    updateTrack: ['playlists', 'mutation', 'update-track'],
    youtubeAutoSearchUrlSingleTrack: ['playlists', 'mutation', 'youtube', 'auto-search-url-single-track'],
    youtubeAutoSearchUrlAllTracks: ['playlists', 'mutation', 'youtube', 'auto-search-url-all-tracks'],
    diskDeleteTrack: ['playlists', 'mutation', 'disk', 'delete-file'],
    diskDownloadSingleTrack: ['playlists', 'mutation', 'disk', 'download-single-track'],
    diskDownloadAllTracks: ['playlists', 'mutation', 'disk', 'download-all-tracks'],
  },
};

export function useAddPlaylist() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationKey: queryKeys.mutation.updateTrack,
    mutationFn: (
      payload: Parameters<typeof apiClient.playlist_addPlaylist>[0]
    ) => apiClient.playlist_addPlaylist(payload),
    onSettled: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.query.playlistList
      });
    }
  });
}

/** Get all playlist items */
export function usePlaylists() {
  return useQuery({
    queryKey: queryKeys.query.playlistList,
    queryFn: async () => {
      const allItems = await apiClient.playlist_getAll();
      const sortedItems = [...allItems].sort((a, b) => a.name.localeCompare(b.name));
      return {
        originalSortedItems: allItems,
        sortedItems,
      };
    }
  });
}

/** Get a single playlist data */
export function usePlaylist(payload: Parameters<typeof apiClient.playlist_getOne>[0]) {
  return useQuery({
    queryKey: queryKeys.query.playlistDetails(payload.playlistId),
    queryFn: () => apiClient.playlist_getOne(payload),
  });
}

/** Refetch "spotify" playlist data, and update persisted data */
export function useMutationPlaylistRefetchSpotifySide() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationKey: queryKeys.mutation.spotifyRefetchPlaylist,
    mutationFn: (
      payload: Parameters<typeof apiClient.playlist_spotify_refetch>[0]
    ) => apiClient.playlist_spotify_refetch(payload),
    onSettled: (_responseData, _error, mutationInput) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.query.playlistDetails(mutationInput.playlistId)
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.query.playlistList
      });
    }
  });
}

/** Update a track of a playlist, and update persisted data */
export function useMutationPlaylistUpdateTrack() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationKey: queryKeys.mutation.updateTrack,
    mutationFn: (
      payload: Parameters<typeof apiClient.playlist_updateTrack>[0]
    ) => apiClient.playlist_updateTrack(payload),
    onSettled: (_responseData, _error, mutationInput) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.query.playlistDetails(mutationInput.playlist_id)
      });
    }
  });
}

/** Find a track youtube url on youtube and update persisted data */
export function useMutationPlaylistFindTrackYoutubeUrlSingleTrack() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationKey: queryKeys.mutation.youtubeAutoSearchUrlSingleTrack,
    mutationFn: (
      payload: Parameters<typeof apiClient.playlist_youtube_autoSearchUrlSingleTrack>[0]
    ) => apiClient.playlist_youtube_autoSearchUrlSingleTrack(payload),
    onSettled: (_responseData, _error, mutationInput) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.query.playlistDetails(mutationInput.playlistId)
      });
    }
  });
}

/** Find Youtube urls for all tracks of a playlist (only if missing) and update persisted data */
export function useMutationPlaylistFindTrackYoutubeUrlAllTracks() {
  return useMutation({
    mutationKey: queryKeys.mutation.youtubeAutoSearchUrlAllTracks,
    mutationFn: (
      payload: Parameters<typeof apiClient.playlist_youtube_autoSearchUrlAllTracks>[0]
    ) => apiClient.playlist_youtube_autoSearchUrlAllTracks(payload),
  });
}


/** Delete a track from disk and update persisted data */
export function useMutationPlaylistDeleteTrackFromDisk() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationKey: queryKeys.mutation.diskDeleteTrack,
    mutationFn: (
      payload: Parameters<typeof apiClient.playlist_disk_deleteFile>[0]
    ) => apiClient.playlist_disk_deleteFile(payload),
    onSettled: (_responseData, _error, mutationInput) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.query.playlistDetails(mutationInput.playlistId)
      });
    }
  });
}

/** Download a track from youtube and update persisted data */
export function useMutationPlaylistDownloadSingleTrack() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationKey: queryKeys.mutation.diskDownloadSingleTrack,
    mutationFn: (
      payload: Parameters<typeof apiClient.playlist_disk_downloadSingleTrack>[0]
    ) => apiClient.playlist_disk_downloadSingleTrack(payload),
    onSettled: (_responseData, _error, mutationInput) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.query.playlistDetails(mutationInput.playlistId)
      });
    }
  });
}

/** Download all (missing) tracks from youtube and update persisted data */
export function useMutationPlaylistDownloadAllTracks() {
  return useMutation({
    mutationKey: queryKeys.mutation.diskDownloadAllTracks,
    mutationFn: (
      payload: Parameters<typeof apiClient.playlist_disk_downloadAllTracks>[0]
    ) => apiClient.playlist_disk_downloadAllTracks(payload),
  });
}
