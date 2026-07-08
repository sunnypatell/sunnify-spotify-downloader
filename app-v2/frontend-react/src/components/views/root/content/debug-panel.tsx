
import { useGlobalDebugVisibility } from "@/state/global.debug-visibility";
import { useGlobalEventsLogs } from "#/state/global.backend-events";
import { CONSTANTS } from "@/constants";

import { DebugOnly } from "#/components/ui/debug.with-state";
import {
  DebugPanelTogglerButton,
  DebugPanelWrapper,
  DebugPanelTab,
  DebugPanelTabHeader,
  DebugPanelTabContent,
} from "#/components/ui/debug-panel";
import { DebugEventLogsList, DebugEventLogsItem } from "#/components/ui/debug-panel.event-logs";
import { DebugConstants } from "#/components/ui/debug-panel.constants";
import { useFirstRender } from "#/utils/hooks/use-first-render";


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
        <TabEventsLogs />
        <TabConstants />
      </DebugPanelWrapper>
    </DebugOnly>
  );
}

function TabEventsLogs() {
  const eventsLogs = useGlobalEventsLogs();

  return (
    <DebugPanelTab className="flex-3">
      <DebugPanelTabHeader>Events Logs</DebugPanelTabHeader>
      <DebugPanelTabContent>
        <DebugEventLogsList>
          {eventsLogs.map((event, index) => (
            <DebugEventLogsItem
              key={index}
              event={event}
            />)
          )}
        </DebugEventLogsList>
      </DebugPanelTabContent>
    </DebugPanelTab>
  );
}

function TabConstants() {
  const isFirstRender = useFirstRender();

  if (isFirstRender) {
    return null;
  }

  return (
    <DebugPanelTab className="flex-1">
      <DebugPanelTabHeader>Constants</DebugPanelTabHeader>
      <DebugPanelTabContent>
        <DebugConstants constantsObject={CONSTANTS} />
      </DebugPanelTabContent>
    </DebugPanelTab>
  );
}