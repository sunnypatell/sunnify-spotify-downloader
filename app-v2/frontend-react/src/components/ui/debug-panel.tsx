import { cn } from "#/lib/utils";
import { Button } from "./button";
import { Switch } from "./switch";

export function DebugPanelTogglerButton({
  isEnabled,
  toggleIsEnabled,
}: {
  isEnabled: boolean,
  toggleIsEnabled: () => void,
}) {
  return (
    <Button
      onClick={toggleIsEnabled}
      variant="secondary"
    >
      Debug
      <Switch
        checked={isEnabled}
        className="pointer-events-none"
      />
    </Button>
  );
}

export function DebugPanelWrapper({ children }: { children: React.ReactNode; }) {
  return (
    <div className="min-h-0 min-w-0 h-70 w-full max-w-full flex flex-col border-t bg-muted/40">
      {/* <p className="px-4 py-3 border-b text-xs/none text-foreground">
        Debug Panel
      </p> */}
      <div className="min-h-0 flex-1 flex">
        {children}
      </div>
    </div>
  );
}

export function DebugPanelTab({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: React.ComponentProps<"div">["className"];
}) {
  return (
    <div className={cn("min-h-0 min-w-0 h-full flex-1 flex flex-col not-first:border-l", className)}>
      {children}
    </div>
  );
}

export function DebugPanelTabHeader({ children }: { children: React.ReactNode; }) {
  return (
    <div className="px-4 py-3 border-b text-xs/none text-muted-foreground">
      {children}
    </div>
  );
}
export function DebugPanelTabContent({ children }: { children: React.ReactNode; }) {
  return (
    <div className="flex-1 overflow-auto flex flex-col-reverse">
      {children}
    </div>
  );
}


