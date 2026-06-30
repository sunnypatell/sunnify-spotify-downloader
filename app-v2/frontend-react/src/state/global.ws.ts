import { atom, useAtomValue, useSetAtom } from "jotai";

const atomGlobalWS = atom<null | WebSocket>(null);

export const useGlobalWebSocket = () => {
  const ws = useAtomValue(atomGlobalWS);
  const isConnected = ws?.readyState === 1;
  return { ws, isConnected };
};

export const useGlobalWebSocketActions = () => {
  const setWebSocket = useSetAtom(atomGlobalWS);
  return {
    setWebSocket,
  };
};