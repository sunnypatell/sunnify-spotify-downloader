import { createFileRoute } from '@tanstack/react-router';
import { RootSidebarContentMain } from '@/components/ui/root';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '#/components/ui/card';
import { Badge } from '@/components/ui/badge';

export const Route = createFileRoute('/')({
  component: RouteComponent,
  pendingComponent: RouteComponent,
});

function RouteComponent() {
  return (
    <RootSidebarContentMain>
      <div className="size-full px-8 py-12 flex flex-col items-center justify-center">
        <h1 className="max-w-3xl text-7xl font-normal tracking-tighter">
          SpotiDisk
        </h1>
        <p className="mt-8 max-w-3xl text-2xl/relaxed tracking-tight text-muted-foreground text-center">
          Spotify Playlists downloader with granular workflow
        </p>
        <div className="mt-16 w-full max-w-5xl grid grid-cols-2 gap-8">
          <CardInstruction
            number={1}
            title="Add Spotify Playlist"
            description={
              <>
                Navigate to <Badge variant="outline" render={<Link to="/add-playlist">Add Playlist</Link>} /> to add a playlist from Spotify using the link of the playlist.
                <br />Playlist must be public (you don't need to link your Spotify account to the App).
                <br />The playlist will appear in the left Sidebar.
              </>
            }
          />
          <CardInstruction
            number={2}
            title="Link to Youtube"
            description={
              <>
                Link each Playlist track to a Youtube video,
                using <Badge variant="outline">Auto-Search Youtube URL</Badge>
                or manually <Badge variant="outline">Set Youtube Url</Badge>.
                <br />Both these features are available for single track or the whole playlist.
              </>
            }
          />
          <CardInstruction
            number={3}
            title="Correct Youtube links"
            description={
              <>
                Use <Badge variant="outline">Spotify Preview</Badge> and <Badge variant="outline">Youtube Preview</Badge> features to check that the linked track is the one that you want.
                In case of a mismatch, use <Badge variant="outline">Set Youtube Url</Badge> to overwrite it.
              </>
            }
          />
          <CardInstruction
            number={4}
            title="Download Tracks"
            description={
              <>
                Download tracks to your computer as mp3, indivually or in bulk (whole playlist).
                <br />Then check the downloaded file with <Badge variant="outline">Disk File Preview</Badge>.
              </>
            }
          />
        </div>
      </div>
    </RootSidebarContentMain>
  );
}


function CardInstruction({
  number,
  title,
  description,
}: {
  number: number,
  title: string,
  description: React.ReactNode;
}) {
  return (
    <Card className="pt-8 pb-12 px-2">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-xl/relaxed font-medium tracking-tight">
          <Badge
            variant="outline"
            className="size-8 text-[0.8em]/none"
          >
            {number}
          </Badge>
          <span className="">
            {title}
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <CardDescription
          className={
            "text-lg/[1.75]"
            + " **:data-[slot=badge]:text-[0.9em]/relaxed"
            + " **:data-[slot=badge]:p-[0.8em_0.75em]"
          }
        >
          {description}
        </CardDescription>
      </CardContent>
    </Card>
  );
}