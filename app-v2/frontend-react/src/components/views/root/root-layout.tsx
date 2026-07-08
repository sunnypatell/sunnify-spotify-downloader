import type { ReactNode } from 'react';

import { AppSidebarHeaderContent } from './sidebar/header-content';
import { AppSidebarNavGroupPlaylists } from './sidebar/nav-group-playlists';
import { AppSidebarNavGroupJobProgress } from './sidebar/nav-group-job-progress';
import { DebugPanel } from './content/debug-panel';
import { AppStatusBar } from './bottom-bar/app-status-bar';

import {
  RootWrapper,
  RootBottomBar,
} from '@/components/ui/root';
import {
  SidebarProvider,
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarInset,
  SidebarRail,
  SidebarHeader,
} from '@/components/ui/sidebar';
import { Button } from '#/components/ui/button';
import { Link } from '@tanstack/react-router';

interface RootLayoutProps {
  children: ReactNode;
}

export function RootLayout({ children }: RootLayoutProps) {
  return (
    <RootWrapper>
      <SidebarProvider
        defaultOpen={true}
        className={
          "min-h-0 flex-1 relative"
          + " **:data-[slot=sidebar-container]:absolute"
          + " **:data-[slot=sidebar-container]:h-full"
        }
      >
        <Sidebar
          variant="sidebar"
          collapsible="offcanvas"
          className="border-r"
        >
          <SidebarHeader className="min-h-16 px-4 py-2 justify-center border-b">
            <AppSidebarHeaderContent />
          </SidebarHeader>
          <SidebarContent className="pb-2">
            <SidebarGroup className="min-h-0 flex-1">
              <SidebarGroupLabel>
                Playlists
              </SidebarGroupLabel>
              <SidebarGroupContent className="flex-1 overflow-auto no-scrollbar scroll-fade">
                <AppSidebarNavGroupPlaylists />
              </SidebarGroupContent>
            </SidebarGroup>
            <SidebarGroup className="mt-auto">
              <SidebarGroupLabel>
                Jobs
              </SidebarGroupLabel>
              <SidebarGroupContent>
                <AppSidebarNavGroupJobProgress />
              </SidebarGroupContent>
            </SidebarGroup>
          </SidebarContent>
          <SidebarFooter className="border-t p-4">
            <div className="flex flex-col gap-2">
              <Button
                variant="outline"
                className="w-full"
                render={<Link to="/add-playlist">Add Playlist</Link>}
                nativeButton={false}
              />
              <Button
                variant="outline"
                className="w-full"
                render={<Link to="/settings">Settings</Link>}
                nativeButton={false}
              />
            </div>
          </SidebarFooter>
          <SidebarRail />
        </Sidebar>
        <SidebarInset className="min-w-0">
          {children}
          <DebugPanel />
        </SidebarInset>
      </SidebarProvider>
      <RootBottomBar>
        <AppStatusBar />
      </RootBottomBar>
    </RootWrapper>
  );
}


