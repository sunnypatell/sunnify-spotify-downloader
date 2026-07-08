import { createFileRoute } from '@tanstack/react-router';
import { FormAddPlaylist } from '#/components/views/playlist-add-form';
import { RootSidebarContentMain, RootSidebarContentTopBar } from '@/components/ui/root';

export const Route = createFileRoute('/add-playlist')({
  component: RouteComponent,
});

function RouteComponent() {
  return (
    <>
      <RootSidebarContentTopBar>
        <h1 className="font-semibold">
          Add playlist
        </h1>
      </RootSidebarContentTopBar>
      <RootSidebarContentMain>
        <FormAddPlaylist />
      </RootSidebarContentMain>
    </>
  );
}
