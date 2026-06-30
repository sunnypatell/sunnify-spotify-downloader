import { SiSpotify, SiYoutube } from "@icons-pack/react-simple-icons";
import { HardDriveIcon } from "lucide-react";

import type { DerivedPlaylist } from "@/lib/api-client/types";
import {
  useMutationPlaylistRefetchSpotifySide,
  useMutationPlaylistDownloadAllTracks,
  useMutationPlaylistFindTrackYoutubeUrlAllTracks,
} from "#/data/use-playlists";
import { useMutationUtilsDiskRevealInFinder } from "#/data/use-utils";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { TooltipEasy } from "@/components/ui/tooltip-easy";

export function PlaylistActions({
  playlist
}: {
  playlist: DerivedPlaylist;
}) {

  const mutationPlaylistRefetchSpotifySide = useMutationPlaylistRefetchSpotifySide();
  const mutationUtilsDiskRevealInFinder = useMutationUtilsDiskRevealInFinder();
  const mutationPlaylistDownloadAllTracks = useMutationPlaylistDownloadAllTracks();
  const mutationPlaylistAutoSearchYoutubeUrl = useMutationPlaylistFindTrackYoutubeUrlAllTracks();

  return (
    <div className="px-3 py-3 flex flex-wrap justify-between gap-8 border rounded-md">

      <div className="flex-1 flex flex-wrap gap-2 items-center content-between">
        <p className="w-full font-medium text-sm">Spotify</p>
        <TooltipEasy tooltipText="Spotify Playlist ID" classNameTrigger="w-full">
          <Badge variant="outline">
            {playlist.spotify_id}
          </Badge>
        </TooltipEasy>
        <TooltipEasy tooltipText="Refetch playlist data from Spotify (required when Spotify side is changed and you want to sync to it!)">
          <Button
            onClick={() => mutationPlaylistRefetchSpotifySide.mutate({
              playlistId: playlist.spotify_id,
              playlistName: playlist.name,
            })}
            disabled={mutationPlaylistRefetchSpotifySide.isPending}
            isLoading={mutationPlaylistRefetchSpotifySide.isPending}
            variant="secondary"
          >
            <SiSpotify />
            Fetch
          </Button>
        </TooltipEasy>
        <TooltipEasy tooltipText="View the playlist on Spotify in a new tab">
          <Button
            variant="secondary"
            nativeButton={false}
            render={(
              <a
                href={playlist.spotify_url}
                target="_blank"
                rel="noopener noreferrer"
              >
                <SiSpotify />
                View
              </a>
            )}
          />
        </TooltipEasy>
      </div>

      <div className="flex-1 flex flex-wrap gap-2 items-center content-between">
        <p className="w-full font-medium text-sm">Youtube</p>
        <TooltipEasy tooltipText="Do Youtube 'Auto-Search URL' for all tracks that don't have one in this playlist">
          <Button
            onClick={() => mutationPlaylistAutoSearchYoutubeUrl.mutate({
              playlistId: playlist.spotify_id,
            })}
            disabled={mutationPlaylistAutoSearchYoutubeUrl.isPending}
            isLoading={mutationPlaylistAutoSearchYoutubeUrl.isPending}
            variant="secondary"
          >
            <SiYoutube />
            Auto Search URL
          </Button>
        </TooltipEasy>
      </div>

      <div className="flex-1 flex flex-wrap gap-2 items-center content-between">
        <p className="w-full font-medium text-sm">Disk</p>
        <TooltipEasy
          tooltipText="Th path of this playlist on your computer, where the tracks are stored"
          classNameTrigger="w-full"
        >
          <Badge variant="outline">
            {playlist.disk_path}
          </Badge>
        </TooltipEasy>
        <TooltipEasy tooltipText="Open the playlist folder on your computer">
          <Button
            onClick={() => mutationUtilsDiskRevealInFinder.mutate({
              path: playlist.disk_path
            })}
            disabled={mutationUtilsDiskRevealInFinder.isPending}
            isLoading={mutationUtilsDiskRevealInFinder.isPending}
            variant="secondary"
          >
            <HardDriveIcon />
            Open
          </Button>
        </TooltipEasy>
        <TooltipEasy tooltipText="Download all missing tracks of this playlist. Only tracks that have Youtube linke and are not yet downloaded will be downloaded!">
          <Button
            onClick={() => mutationPlaylistDownloadAllTracks.mutate({
              playlistId: playlist.spotify_id,
            })}
            disabled={mutationPlaylistDownloadAllTracks.isPending}
            isLoading={mutationPlaylistDownloadAllTracks.isPending}
            variant="secondary"
          >
            <HardDriveIcon />
            Download All
          </Button>
        </TooltipEasy>
      </div>

    </div>
  );
}