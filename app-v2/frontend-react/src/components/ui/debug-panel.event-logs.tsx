import type { EventItem } from "#/state/global.backend-events";
import { utilsJson } from "#/utils/json";

export function DebugEventLogsList({ children }: { children: React.ReactNode; }) {
  return (
    <div className="flex flex-col-reverse">
      {children}
    </div>
  );
}

export function DebugEventLogsItem({ event }: { event: EventItem; }) {
  const text = utilsJson.stringify(event);
  return (
    <div className="min-w-full px-2 py-2 border-b text-xs text-muted-foreground whitespace-nowrap">
      {text}
    </div>
  );
}