import { createFileRoute } from '@tanstack/react-router';

import { usePlaylist } from '@/data/use-playlists';
import type { DerivedPlaylist } from '@/lib/api-client/types';

import { PlaylistActions } from '@/components/views/playlist-actions';
import { PlaylistTracksTable } from '@/components/views/playlist-tracks-table';

import { RootSidebarContentMain, RootSidebarContentTopBar } from '@/components/ui/root';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert } from '@/components/ui/alert';

export const Route = createFileRoute('/playlist/$playlistId')({
  component: RouteComponent,
});

function RouteComponent() {
  const { playlistId } = Route.useParams();
  const queryPlaylist = usePlaylist({ playlistId });

  if (queryPlaylist.isLoading) {
    return <PlaylistLoading />;
  }

  if (queryPlaylist.isError) {
    return <PlaylistError playlistId={playlistId} />;
  }

  if (!queryPlaylist.data) {
    return <PlaylistNotFound playlistId={playlistId} />;
  }

  return <PlaylistView playlist={queryPlaylist.data} />;
}


function PlaylistLoading() {
  return (
    <>
      <RootSidebarContentTopBar>
        <Skeleton className="w-50 h-8" />
      </RootSidebarContentTopBar>
      <RootSidebarContentMain>
        {null}
      </RootSidebarContentMain>
    </>
  );
}

function PlaylistNotFound({ playlistId }: { playlistId: string; }) {
  return (
    <>
      <RootSidebarContentTopBar>
        Playlist {playlistId} not found
      </RootSidebarContentTopBar>
      <RootSidebarContentMain>
        <Alert variant="destructive">
          Playlist {playlistId} not found
        </Alert>
      </RootSidebarContentMain>
    </>
  );
}

function PlaylistError({ playlistId }: { playlistId: string; }) {
  return (
    <>
      <RootSidebarContentTopBar>
        Error loading playlist {playlistId}
      </RootSidebarContentTopBar>
      <RootSidebarContentMain>
        <Alert variant="destructive">
          There was an error loading playlist {playlistId}
        </Alert>
      </RootSidebarContentMain>
    </>
  );
}

function PlaylistView({ playlist }: { playlist: DerivedPlaylist; }) {
  return (
    <>
      <PlaylistHeaderBar playlist={playlist} />
      <PlaylistContent playlist={playlist} />
    </>
  );
}

function PlaylistHeaderBar({ playlist }: { playlist: DerivedPlaylist; }) {
  const queryPlaylist = usePlaylist({ playlistId: playlist.spotify_id });

  return (
    <RootSidebarContentTopBar>
      <h1 className="w-full font-semibold">{playlist.name}</h1>
      <Button
        variant="secondary"
        onClick={() => queryPlaylist.refetch()}
      >
        Refresh
      </Button>
    </RootSidebarContentTopBar>
  );
}

function PlaylistContent({ playlist }: { playlist: DerivedPlaylist; }) {
  return (
    <RootSidebarContentMain>
      <PlaylistActions playlist={playlist} />
      <div className="min-h-0 flex-1 flex flex-col">
        <PlaylistTracksTable tracks={playlist.tracks} />
      </div>
    </RootSidebarContentMain>
  );
}