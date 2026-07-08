import { Badge } from "#/components/ui/badge";
import { CONSTANTS } from "@/constants";
import { useFirstRender } from "#/utils/hooks/use-first-render";

export function AppStatusBar() {
  const isFirstRender = useFirstRender();

  if (isFirstRender) {
    return null;
  }

  return (
    <div className="flex flex-row gap-2 items-center text-xs text-muted-foreground">
      <span>
        SpotiDisk
      </span>
      <span>
        v{CONSTANTS.APP_VERSION}
      </span>
      {CONSTANTS.FRONTEND_APP_MODE === 'DEV' && (
        <Badge variant="outline">DEV</Badge>
      )}
    </div>
  );
}