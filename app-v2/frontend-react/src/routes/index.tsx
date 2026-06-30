import { createFileRoute } from '@tanstack/react-router';
import { RootContentMain, RootContentTopBar } from '@/components/ui/root';

export const Route = createFileRoute('/')({
  component: RouteComponent,
});

function RouteComponent() {
  return (
    <>
      <RootContentTopBar>
        Home
      </RootContentTopBar>
      <RootContentMain>
        {null}
      </RootContentMain>
    </>
  );
}
