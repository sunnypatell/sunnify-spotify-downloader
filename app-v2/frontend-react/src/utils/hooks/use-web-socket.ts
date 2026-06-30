import { useEffect } from "react";

export function useWebSocketConnection({
  initWsConnection,
  onConnected,
  onDisconnected,
  onMessageFromBackend,
}: {
  initWsConnection: () => WebSocket;
  onConnected?: (ws: WebSocket) => void;
  onDisconnected?: (ws: WebSocket) => void;
  onMessageFromBackend?: (event: MessageEvent<any>) => void;
}) {
  useEffect(
    () => {
      // connect (send request to backend)
      const ws = initWsConnection();

      // add event listeners
      const handlers = {
        onOpen: () => { onConnected?.(ws); },
        onClose: () => { onDisconnected?.(ws); },
        onError: (event: Event) => { console.error(event); },
        onMessage: (event: MessageEvent) => { onMessageFromBackend?.(event); },
      };
      ws.addEventListener('open', handlers.onOpen);
      ws.addEventListener('close', handlers.onClose);
      ws.addEventListener('error', handlers.onError);
      ws.addEventListener('message', handlers.onMessage);

      // on component unmount
      return () => {
        // remove event listeners
        ws.removeEventListener('open', handlers.onOpen);
        ws.removeEventListener('close', handlers.onClose);
        ws.removeEventListener('error', handlers.onError);
        ws.removeEventListener('message', handlers.onMessage);

        // close connection
        ws.close();
      };
    },
    []
  );

  return null;
}