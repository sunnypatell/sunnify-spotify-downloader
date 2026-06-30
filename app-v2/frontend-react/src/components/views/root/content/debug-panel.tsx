
import { useGlobalDebugVisibility } from "@/state/global.debug-visibility";
import { useGlobalEventsLogs } from "#/state/global.backend-events";

import { DebugOnly } from "#/components/ui/debug.with-state";
import { DebugPanelTogglerButton, DebugPanelWrapper } from "#/components/ui/debug-panel";
import { DebugEventLogsList, DebugEventLogsItem } from "#/components/ui/debug-panel.event-logs";

export function DebugPanelToggler() {
  const debugVisibility = useGlobalDebugVisibility();
  return (
    <DebugPanelTogglerButton
      isEnabled={debugVisibility.isVisible}
      toggleIsEnabled={debugVisibility.toggleIsVisible}
    />
  );
}

export function DebugPanel() {
  return (
    <DebugOnly>
      <DebugPanelWrapper>
        <EventsLogs />
      </DebugPanelWrapper>
    </DebugOnly>
  );
}

function EventsLogs() {
  const eventsLogs = useGlobalEventsLogs();

  return (
    <DebugEventLogsList>
      {eventsLogs.map((event, index) => (
        <DebugEventLogsItem
          key={index}
          event={event}
        />)
      )}
    </DebugEventLogsList>
  );
}