import { Button } from "./button";
import { Switch } from "./switch";

export function DebugPanelWrapper({ children }: { children: React.ReactNode; }) {
  return (
    <div className="min-h-0 min-w-0 h-70 w-full max-w-full overflow-hidden flex flex-col border-t bg-muted/20">
      <p className="px-4 py-3 text-xs/none text-muted-foreground border-b">
        Debug Panel
      </p>
      <div className="min-h-0 flex-1 flex flex-col">
        {children}
      </div>
    </div>
  );
}


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
      <Switch checked={isEnabled} />
    </Button>
  );
}