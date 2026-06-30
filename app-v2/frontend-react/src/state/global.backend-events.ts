import { atom, useAtomValue, useSetAtom } from "jotai";

export type EventItem = Record<string, unknown>;

const atomGlobalEventsLogs = atom<EventItem[]>([]);

export const useGlobalEventsLogs = () => useAtomValue(atomGlobalEventsLogs);
export const useGlobalEventsLogsActions = () => {
  const set = useSetAtom(atomGlobalEventsLogs);
  const addEvent = (event: EventItem) => set((state) => [...state, event]);
  return {
    addEvent,
  };
};