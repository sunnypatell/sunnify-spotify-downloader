import { createFileRoute } from '@tanstack/react-router';
import { FormAddPlaylist } from '#/components/views/playlist-add-form';
import { RootContentMain, RootContentTopBar } from '@/components/ui/root';

export const Route = createFileRoute('/add-playlist')({
  component: RouteComponent,
});

function RouteComponent() {
  return (
    <>
      <RootContentTopBar>
        <h1 className="font-semibold">
          Add playlist
        </h1>
      </RootContentTopBar>
      <RootContentMain>
        <FormAddPlaylist />
      </RootContentMain>
    </>
  );
}
