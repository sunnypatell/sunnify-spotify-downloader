import { atom, useAtomValue, useSetAtom } from "jotai";
import type { WsBackendEvent } from "#/lib/api-client/types";

type JobProgressState = Extract<WsBackendEvent['payload'], { kind: 'JOB_PROGRESS'; }>;
const initialState: JobProgressState = {
  kind: 'JOB_PROGRESS',
  dateTimeISO: new Date().toISOString(),
  jobs: []
};

export const atomGlobalJobProgress = atom<JobProgressState>(initialState);

export const useGlobalJobProgress = () => useAtomValue(atomGlobalJobProgress);
export const useGlobalJobProgressActions = () => {
  const setJobProgress = useSetAtom(atomGlobalJobProgress);
  return {
    setJobProgress,
  };
};