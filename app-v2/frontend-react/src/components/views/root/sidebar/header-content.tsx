import { Link } from "@tanstack/react-router";
import { DebugPanelToggler } from "../content/debug-panel";
import { SidebarTrigger } from "#/components/ui/sidebar";

export function AppSidebarHeaderContent() {
  return (
    <div
      className="flex items-center gap-4 *:last:ml-auto"
    >
      <SidebarTrigger />
      <Link
        to="/"
        className="text-xl font-semibold"
      >
        SpotiDisk
      </Link>
      <DebugPanelToggler />
    </div>
  );
}