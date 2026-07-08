import { createFileRoute } from '@tanstack/react-router';
import { RootSidebarContentMain, RootSidebarContentTopBar } from '@/components/ui/root';

export const Route = createFileRoute('/')({
  component: RouteComponent,
});

function RouteComponent() {
  return (
    <>
      <RootSidebarContentTopBar>
        Home
      </RootSidebarContentTopBar>
      <RootSidebarContentMain>
        {null}
      </RootSidebarContentMain>
    </>
  );
}
