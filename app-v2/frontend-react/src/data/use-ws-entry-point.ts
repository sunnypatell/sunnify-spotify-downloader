import { useQueryClient } from "@tanstack/react-query";

import { apiClient } from "#/lib/api-client/client.singleton";

import { useGlobalWebSocketActions } from "#/state/global.ws";
import { useGlobalEventsLogsActions } from "#/state/global.backend-events";
import { useGlobalJobProgressActions } from "#/state/global.job-progress";

import { useWebSocketConnection } from "#/utils/hooks/use-web-socket";
import { toast } from "#/components/ui/sonner";


export function useWsEntryPoint() {

  const queryClient = useQueryClient();
  const wsActions = useGlobalWebSocketActions();
  const eventsLogsActions = useGlobalEventsLogsActions();
  const jobProgressActions = useGlobalJobProgressActions();

  return useWebSocketConnection({
    initWsConnection: () => apiClient.wsEntryPointConnect().getWs(),
    onConnected: (ws) => {
      wsActions.setWebSocket(ws);
      eventsLogsActions.addEvent({ data: ['useWsEntryPoint', 'Connected to backend'] });
      toast.success('Connected to backend');
    },
    onDisconnected: () => {
      wsActions.setWebSocket(null);
      eventsLogsActions.addEvent({ data: ['useWsEntryPoint ', 'Disconnected from backend'] });
      toast.error('Disconnected from backend');
    },
    onMessageFromBackend: (event) => {
      try {
        // parse ws message
        const schema = apiClient.wsEntryPointConnect()._responseDataSchema;
        const backendEvent = schema.parse(JSON.parse(event.data));
        const nowIso = new Date().toISOString();
        // based on event type do something
        switch (backendEvent.payload.kind) {
          case "MESSAGE":
            eventsLogsActions.addEvent({ receivedAt: nowIso, data: backendEvent });
            if (backendEvent.payload.severity === "INFO") toast.message(backendEvent.payload.text);
            else if (backendEvent.payload.severity === "WARNING") toast.warning(backendEvent.payload.text);
            else if (backendEvent.payload.severity === "ERROR") toast.error(backendEvent.payload.text);
            else if (backendEvent.payload.severity === "SUCCESS") toast.success(backendEvent.payload.text);
            break;
          case "FRONTEND_QUERY_INVALIDATION":
            eventsLogsActions.addEvent({ receivedAt: nowIso, data: backendEvent });
            queryClient.invalidateQueries({ queryKey: backendEvent.payload.queryKeys });
            break;
          case "JOB_PROGRESS":
            eventsLogsActions.addEvent({ receivedAt: nowIso, data: backendEvent });
            jobProgressActions.setJobProgress(backendEvent.payload);
            break;
          default:
            break;
        }
      } catch (error) {
        eventsLogsActions.addEvent({ data: [/*`useWsEntryPoint`, `🏠 BE`, */`ERROR: parsing ws message`, event, error] });
        console.log([`useWsEntryPoint`, `🏠 BE`, `ERROR: parsing ws message`, event, error]);
        toast.error(`Error processing server message!`);
      }
    }
  });
}