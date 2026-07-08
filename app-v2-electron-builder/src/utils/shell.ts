import { spawn, spawnSync, type ChildProcess } from "node:child_process";

export type { ChildProcess };

export const utilsShell = {
  launchProcess: spawn,
  launchProcessSync: spawnSync,
  killProcess: (childProcess?: ChildProcess | null) => {
    childProcess?.kill();
  }
};