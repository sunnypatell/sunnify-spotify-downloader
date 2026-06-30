import { Link } from "@tanstack/react-router";

import { NavGroupJobProgress } from "./nav-group-job-progress";
import { NavGroupPlaylists } from "./nav-group-playlists";

import {
  Sidebar,
  SidebarHeader,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarGroupContent,
} from "#/components/ui/sidebar";
import { Button } from "#/components/ui/button";
import { DebugPanelToggler } from "../content/debug-panel";

export function RootSidebar() {
  return (
    <Sidebar className="border-r">
      <SidebarHeader className="min-h-16 border-b px-6 py-2 flex flex-row items-center justify-between">
        <Link to="/" className="text-xl font-semibold">SpotiDisk</Link>
        <DebugPanelToggler />
      </SidebarHeader>
      <SidebarContent>

        <SidebarGroup className="min-h-0 flex-1">
          <SidebarGroupLabel>
            Playlists
          </SidebarGroupLabel>
          <SidebarGroupContent className="flex-1 overflow-auto">
            <NavGroupPlaylists />
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarGroup className="mt-auto">
          <SidebarGroupLabel>
            Jobs
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <NavGroupJobProgress />
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
    </Sidebar>
  );
}