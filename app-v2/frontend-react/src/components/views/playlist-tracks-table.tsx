import type { ColumnDef } from "@tanstack/react-table";
import { SiSpotify, SiYoutube } from '@icons-pack/react-simple-icons';
import {
  CopyIcon,
  DeleteIcon,
  DownloadIcon,
  HardDriveIcon,
  InfoIcon,
  PencilIcon,
  PlayIcon,
  SearchIcon,
  TagIcon,
  TrashIcon,
} from "lucide-react";

import type { DerivedTrack } from "@/lib/api-client/types";
import { apiClient } from "@/lib/api-client/client.singleton";
import {
  useMutationPlaylistDeleteTrackFromDisk,
  useMutationPlaylistDownloadSingleTrack,
  useMutationPlaylistFindTrackYoutubeUrlSingleTrack,
  useMutationPlaylistUpdateTrack
} from "#/data/use-playlists";

import { useCopyToClipboard } from "#/utils/hooks/use-copy-to-clipboard";

import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { IconIsInvalid, IconIsValid } from "@/components/ui/icons-common";
import { TimeDurationMMSS } from "@/components/ui/time";
import { TooltipEasy } from "@/components/ui/tooltip-easy";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { PlayerYoutube } from "@/components/ui/player-youtube";
import { DebugOnly } from "@/components/ui/debug.with-state";

const columns: ColumnDef<DerivedTrack>[] = [
  {
    id: "track_number",
    header: () => (
      <span className="pl-1 flex gap-2 items-center">
        #
      </span>
    ),
    size: 50,
    cell: ({ row }) => {
      return (
        <div className="flex items-center gap-1 text-sm">
          <span>
            {row.index + 1}
          </span>
          <DebugOnly>
            <TooltipEasy
              classNameContent="w-180 max-w-[initial]"
              tooltipText={(
                <pre className="w-180 overflow-auto">
                  {JSON.stringify(row.original, null, 2)}
                </pre>
              )}
            >
              <InfoIcon className="size-[1em] text-muted-foreground" />
            </TooltipEasy>
          </DebugOnly>
        </div>
      );
    },
  },
  {
    id: "cover_image",
    header: "Cover",
    size: 100,
    cell: ({ row }) => {
      return (
        <div className="size-18 bg-muted overflow-hidden">
          {row.original.cover_url && (
            <img
              src={row.original.cover_url}
              alt={row.original.title}
              className="size-full object-cover"
            />
          )}
        </div>
      );
    }
  },
  {
    id: "song",
    accessorFn: (row) => row.title,
    header: "Song",
    // size: 220,
    // minSize: 220,
    cell: ({ row }) => {
      return (
        <div className="flex flex-col gap-1 pr-4">
          <span className="font-medium text-foreground">{row.original.title}</span>
          <span className="text-xs text-muted-foreground">{row.original.artists}</span>
          <span className="text-xs text-muted-foreground">ALB: {row.original.album || '-'}</span>
          <span className="text-xs text-muted-foreground">LAB: {row.original.recording_label ?? '-'}</span>
        </div>
      );
    },
  },
  {
    id: "spotify",
    accessorFn: (row) => row.spotify_id,
    header: () => (
      <span className="pl-1 flex gap-2 items-center">
        <SiSpotify className="size-4" /> Spotify
      </span>
    ),
    // size: 100,
    // minSize: 170,
    cell: ({ row }) => {
      return (
        <div className="flex gap-2 items-center pr-4">
          <TooltipEasy tooltipText="Open track in Spotify">
            <Button
              variant="secondary"
              size="icon"
              nativeButton={false}
              render={(
                <a
                  href={row.original.spotify_url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <SiSpotify />
                </a>
              )}
            />
          </TooltipEasy>
          <TimeDurationMMSS
            type="mm:ss"
            durationString={row.original.spotify_duration_mm_ss}
          />
          <Dialog>
            <TooltipEasy tooltipText="Open audio preview in Spotify">
              <DialogTrigger
                render={(
                  <Button
                    variant="secondary"
                    size="icon"
                    disabled={!row.original.spotify_preview_url}
                  >
                    <PlayIcon />
                  </Button>
                )}
              />
            </TooltipEasy>
            <DialogContent className="w-200 sm:max-w-[80dvw]">
              <DialogHeader>
                <DialogTitle>Spotify Audio Preview</DialogTitle>
                <DialogDescription>
                  30 seconds of audio preview of the Spotify track
                </DialogDescription>
              </DialogHeader>
              <audio
                src={row.original.spotify_preview_url}
                controls
                autoPlay
                className="w-full"
              />
            </DialogContent>
          </Dialog>
        </div>
      );
    },
  },
  {
    id: "youtube",
    accessorFn: (row) => row.youtube_url,
    header: () => (
      <span className="pl-1 flex gap-2 items-center">
        <SiYoutube className="size-4" /> YouTube
      </span>
    ),
    // size: 100,
    // minSize: 200,
    cell: ({ row }) => {

      const mutationUpdateTrack = useMutationPlaylistUpdateTrack();
      const mutationFindTrackYoutubeUrl = useMutationPlaylistFindTrackYoutubeUrlSingleTrack();
      const copyToClipboard = useCopyToClipboard();


      const buildManualSearchUrl = (track: DerivedTrack) => {
        const url = new URL("https://www.youtube.com/results");
        url.searchParams.set("search_query", `${track.artists} ${track.title}`);
        return url.toString();
      };

      const handleSetYoutubeUrl = () => {
        const userUrl = prompt("Enter a YouTube URL");
        if (userUrl) {
          mutationUpdateTrack.mutate({
            playlist_id: row.original.spotify_playlist_id,
            track_id: row.original.spotify_id,
            youtube_url: userUrl,
          });
        }
      };
      const handleClearYoutubeUrl = () => {
        mutationUpdateTrack.mutate({
          playlist_id: row.original.spotify_playlist_id,
          track_id: row.original.spotify_id,
          youtube_url: null,
        });
      };
      const handleFindYouTubeUrl = () => {
        mutationFindTrackYoutubeUrl.mutate({
          playlistId: row.original.spotify_playlist_id,
          trackId: row.original.spotify_id,
        });
      };
      const handleCopyYoutubeUrlToClipboard = () => {
        if (!row.original.youtube_url) {
          return;
        }
        copyToClipboard.copy({
          text: row.original.youtube_url,
          showToast: true
        });
      };

      if (!row.original.youtube_url) {
        return (
          <div className="flex gap-2 items-center pr-4">
            <TooltipEasy tooltipText="No Linked YouTube track">
              <IconIsInvalid className="size-5" />
            </TooltipEasy>
            <TooltipEasy tooltipText="Auto Search - Find and set the best YouTube URL match for this track. If nothing is found use manual search">
              <Button
                onClick={handleFindYouTubeUrl}
                isLoading={mutationFindTrackYoutubeUrl.isPending}
                variant="secondary"
                size="icon"
              >
                <SearchIcon />
              </Button>
            </TooltipEasy>
            <TooltipEasy tooltipText="Manual Search - Open Youtube search in new tab with search populated">
              <Button
                variant="secondary"
                size="icon"
                nativeButton={false}
                render={(
                  <a
                    href={buildManualSearchUrl(row.original)}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <SearchIcon />
                  </a>
                )}
              />
            </TooltipEasy>
            <TooltipEasy tooltipText="Set/Update YouTube URL">
              <Button
                onClick={handleSetYoutubeUrl}
                isLoading={mutationUpdateTrack.isPending}
                variant="secondary"
                size="icon"
              >
                <PencilIcon />
              </Button>
            </TooltipEasy>
          </div>
        );
      }

      return (
        <div className="flex gap-2 items-center pr-4">
          <TooltipEasy tooltipText="A Youtube track is linked">
            <IconIsValid className="size-5" />
          </TooltipEasy>
          <Dialog>
            <TooltipEasy tooltipText="Open track in YouTube">
              <DialogTrigger
                render={(
                  <Button
                    variant="secondary"
                    size="icon"
                  >
                    <SiYoutube />
                  </Button>
                )}
              />
            </TooltipEasy>
            <DialogContent className="w-240 sm:max-w-[80dvw]">
              <DialogHeader>
                <DialogTitle>YouTube Track</DialogTitle>
                <DialogDescription>
                  The linked track on Youtube that will be downloaded to disk
                </DialogDescription>
              </DialogHeader>
              <div className="w-full aspect-video">
                <PlayerYoutube
                  src={row.original.youtube_url}
                  controls
                  autoPlay
                />
              </div>
            </DialogContent>
          </Dialog>
          <TooltipEasy tooltipText="Delete YouTube URL for this track (clear it)">
            <Button
              onClick={handleClearYoutubeUrl}
              isLoading={mutationUpdateTrack.isPending}
              variant="secondary"
              size="icon"
            >
              <DeleteIcon className="-translate-x-px" />
            </Button>
          </TooltipEasy>
          <TooltipEasy tooltipText="Update YouTube URL for this track">
            <Button
              onClick={handleSetYoutubeUrl}
              isLoading={mutationUpdateTrack.isPending}
              variant="secondary"
              size="icon"
            >
              <PencilIcon />
            </Button>
          </TooltipEasy>
          <TooltipEasy tooltipText="Copy YouTube URL for this track to clipboard">
            <Button
              onClick={handleCopyYoutubeUrlToClipboard}
              variant="secondary"
              size="icon"
            >
              <CopyIcon />
            </Button>
          </TooltipEasy>
        </div>
      );
    },
  },
  {
    id: "disk",
    accessorFn: (row) => row.disk_file_name,
    header: () => (
      <span className="pl-1 flex gap-2 items-center">
        <HardDriveIcon className="size-4" /> Disk
      </span>
    ),
    // size: 100,
    // minSize: 300,
    cell: ({ row }) => {
      const mutationDownloadTrack = useMutationPlaylistDownloadSingleTrack();
      const mutationDeleteTrack = useMutationPlaylistDeleteTrackFromDisk();

      const handleDownloadTrack = () => {
        mutationDownloadTrack.mutate({
          playlistId: row.original.spotify_playlist_id,
          trackId: row.original.spotify_id
        });
      };
      const handleDeleteTrack = () => {
        mutationDeleteTrack.mutate({
          playlistId: row.original.spotify_playlist_id,
          trackId: row.original.spotify_id
        });
      };

      const hasDiskFile = row.original.has_disk_file;
      if (!hasDiskFile) {
        return (
          <div className="flex gap-2 items-center pr-4">
            <TooltipEasy tooltipText="File on disk not present/not downloaded">
              <IconIsInvalid className="size-5" />
            </TooltipEasy>
            <TooltipEasy tooltipText="Download/Re-download track from YouTube">
              <Button
                onClick={handleDownloadTrack}
                disabled={mutationDownloadTrack.isPending}
                isLoading={mutationDownloadTrack.isPending}
                variant="secondary"
              >
                <DownloadIcon />
                Download
              </Button>
            </TooltipEasy>
          </div>
        );
      }

      return (
        <div className="flex gap-2 items-center pr-4">
          <TooltipEasy tooltipText="File on disk present/ already downloaded">
            <IconIsValid className="size-5" />
          </TooltipEasy>
          <TimeDurationMMSS
            type="mm:ss"
            durationString={row.original.disk_file_duration_mm_ss ?? '- : -'}
          />
          <Dialog>
            <TooltipEasy tooltipText="Play downloaded track from disk">
              <DialogTrigger
                render={(
                  <Button
                    variant="secondary"
                    size="icon"
                  >
                    <PlayIcon />
                  </Button>
                )}
              />
            </TooltipEasy>
            <DialogContent className="w-200 sm:max-w-[80dvw]">
              <DialogHeader>
                <DialogTitle>Disk Track</DialogTitle>
                <DialogDescription>
                  This track is already downloaded to disk
                </DialogDescription>
              </DialogHeader>
              <audio
                src={apiClient.playlist_disk_getAudioFile_BUILD_URL({
                  playlistId: row.original.spotify_playlist_id,
                  trackId: row.original.spotify_id,
                })}
                controls
                autoPlay
                className="w-full"
              />
            </DialogContent>
          </Dialog>
          <Button
            onClick={handleDownloadTrack}
            disabled={mutationDownloadTrack.isPending}
            isLoading={mutationDownloadTrack.isPending}
            variant="secondary"
          >
            <DownloadIcon />
            Re-Download
          </Button>
          <TooltipEasy tooltipText="Delete track from disk">
            <Button
              onClick={handleDeleteTrack}
              disabled={mutationDeleteTrack.isPending}
              isLoading={mutationDeleteTrack.isPending}
              variant="secondary"
              size="icon"
            >
              <TrashIcon />
            </Button>
          </TooltipEasy>
          <Button
            variant="secondary"
            size="icon"
          >
            <TagIcon />
          </Button>
        </div>
      );
    },
  },
  {
    id: "disk_file_name",
    accessorFn: (row) => row.disk_file_name,
    header: () => (
      <span className="flex gap-2 items-center">
        <HardDriveIcon className="size-4" /> Disk File Name
      </span>
    ),
    // size: 100,
    cell: ({ row }) => {
      const copyToClipboard = useCopyToClipboard();

      const handleCopyDiskFileNameToClipboard = () => {
        copyToClipboard.copy({
          text: row.original.disk_file_name,
        });
      };

      return (
        <div className="flex gap-2 items-center pr-4">
          <TooltipEasy tooltipText="Copy disk file name to clipboard">
            <Button
              onClick={handleCopyDiskFileNameToClipboard}
              variant="secondary"
              size="icon"
            >
              <CopyIcon />
            </Button>
          </TooltipEasy>
          <span className="text-xs text-muted-foreground">
            {row.original.disk_file_name}
          </span>
        </div>
      );
    },
  },
  {
    id: "disk_file_path",
    accessorFn: (row) => row.disk_file_path,
    header: () => (
      <span className="flex gap-2 items-center">
        <HardDriveIcon className="size-4" /> Disk File Path
      </span>
    ),
    // size: 100,
    cell: ({ row }) => {
      return (
        <div className="flex gap-2 items-center pr-4">
          <span className="text-xs text-muted-foreground">
            {row.original.disk_file_path}
          </span>
        </div>
      );
    },
  },
];

interface PlaylistTracksTableProps {
  tracks: DerivedTrack[];
}

export function PlaylistTracksTable({ tracks }: PlaylistTracksTableProps) {
  return (
    <DataTable
      columns={columns}
      data={tracks}
      classNameWrapper="h-full *:h-full"
      classNameTHead="sticky top-0 z-10"
    />
  );
}
