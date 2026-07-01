import { spawn, type ChildProcess } from "node:child_process";

export type { ChildProcess };

export const utilsShell = {
  launchProcess: spawn,
  killProcess: (childProcess?: ChildProcess | null) => {
    if (!childProcess) {
      return;
    }
    childProcess.kill();
  }
};