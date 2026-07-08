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
    <div className="flex flex-wrap justify-between border rounded-md overflow-hidden">

      <Block title="Spotify">
        <BlockRow>
          <TooltipEasy tooltipText="Spotify Playlist ID">
            <Badge variant="outline">
              {playlist.spotify_id}
            </Badge>
          </TooltipEasy>
        </BlockRow>
        <BlockRow>
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
        </BlockRow>
      </Block>

      <Block title="Youtube">
        <BlockRow>
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
        </BlockRow>
      </Block>

      <Block title="Disk">
        <BlockRow>
          <TooltipEasy tooltipText="The path of this playlist on your computer, where the tracks are stored">
            <Badge variant="outline">
              {playlist.disk_path}
            </Badge>
          </TooltipEasy>
        </BlockRow>
        <BlockRow>
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
        </BlockRow>
      </Block>

    </div>
  );
}



// ui

function Block({
  title,
  children
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex-1 flex flex-col not-first:border-l">
      <div className="w-full p-3 bg-muted/50 pr-8">
        <p className="w-full font-medium text-sm">
          {title}
        </p>
      </div>
      <div className="flex-1 px-3 pt-4 pb-3 flex flex-col justify-end gap-3">
        {children}
      </div>
    </div>
  );
}

function BlockRow({
  children
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex gap-2 justify-start">
      {children}
    </div>
  );
}
