import { createFileRoute } from '@tanstack/react-router';

import { usePlaylist } from '@/data/use-playlists';
import type { DerivedPlaylist } from '@/lib/api-client/types';

import { PlaylistActions } from '@/components/views/playlist-actions';
import { PlaylistTracksTable } from '@/components/views/playlist-tracks-table';

import { RootContentMain, RootContentTopBar } from '@/components/ui/root';
import { Button } from '@/components/ui/button';
import { Skeleton } from '#/components/ui/skeleton';

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
      <RootContentTopBar>
        <Skeleton className="w-50 h-8" />
      </RootContentTopBar>
      <RootContentMain>
        {null}
      </RootContentMain>
    </>
  );
}

function PlaylistNotFound({ playlistId }: { playlistId: string; }) {
  return (
    <>
      <RootContentTopBar>
        Playlist {playlistId} not found
      </RootContentTopBar>
      <RootContentMain>
        <p>
          Playlist {playlistId} not found
        </p>
      </RootContentMain>
    </>
  );
}

function PlaylistError({ playlistId }: { playlistId: string; }) {
  return (
    <>
      <RootContentTopBar>
        Error loading playlist {playlistId}
      </RootContentTopBar>
      <RootContentMain>
        <p>
          There was an error loading playlist {playlistId}
        </p>
      </RootContentMain>
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
    <RootContentTopBar>
      <h1 className="w-full font-semibold">{playlist.name}</h1>
      <Button
        variant="secondary"
        onClick={() => queryPlaylist.refetch()}
      >
        Refresh
      </Button>
    </RootContentTopBar>
  );
}

function PlaylistContent({ playlist }: { playlist: DerivedPlaylist; }) {
  return (
    <RootContentMain>
      <PlaylistActions playlist={playlist} />
      <div className="min-h-0 flex-1 flex flex-col">
        <PlaylistTracksTable tracks={playlist.tracks} />
      </div>
    </RootContentMain>
  );
}