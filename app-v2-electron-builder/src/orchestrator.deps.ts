import type { BrowserWindow } from "electron";

import { createConstants } from "./constants";
import { Logger, LoggerTransportConsole, LoggerTransportFile } from "./lib/logger";
import type { WebServer } from "./lib/web-server";

import { utilsDisk } from "./utils/disk";
import { utilsOs } from "./utils/os";
import { utilsShell } from "./utils/shell";
import { utilsString } from "./utils/string";
import { utilsPath } from "./utils/path";

export type OrchestratorDeps = Awaited<ReturnType<typeof createOrchestratorDeps>>;

export async function createOrchestratorDeps() {

  const CONSTANTS = await createConstants();

  const LOGGERS = (() => {
    const LOGGER_TRANSPORTS = {
      FILE_ALL: new LoggerTransportFile(CONSTANTS.PATHS.LOG_FILE_PATH),
      CONSOLE_ORC: new LoggerTransportConsole({ color: 'blue' }),
      CONSOLE_BE: new LoggerTransportConsole({ color: 'green' }),
      CONSOLE_FE: new LoggerTransportConsole({ color: 'yellow' }),
    };

    return {
      ORC: new Logger({
        key: '🚐 ORCHESTRATOR',
        transports: [LOGGER_TRANSPORTS.FILE_ALL, LOGGER_TRANSPORTS.CONSOLE_ORC]
      }),
      BE: new Logger({
        key: '🏠 BACKEND',
        transports: [LOGGER_TRANSPORTS.FILE_ALL, LOGGER_TRANSPORTS.CONSOLE_BE]
      }),
      FE: new Logger({
        key: '🧩 FRONTEND',
        transports: [LOGGER_TRANSPORTS.FILE_ALL, LOGGER_TRANSPORTS.CONSOLE_FE]
      }),
    };

  })();

  const UTILS = {
    OS: utilsOs,
    SHELL: utilsShell,
    STRING: utilsString,
    DISK: utilsDisk,
    PATH: utilsPath,
  };

  const INSTANCES: {
    /** child process of backend server launched */
    backendProcess: ReturnType<typeof UTILS['SHELL']['launchProcess']> | null,
    /** child process of frontend server launched (used in dev to run vite directly) */
    frontendProcess: ReturnType<typeof UTILS['SHELL']['launchProcess']> | null,
    /** instance of frontend webserver (used in prod to serve the static react SPA) */
    frontendWebServer: WebServer | null,
    /** instance of Electron WebView (browser window) */
    electronWindow: BrowserWindow | null;
  } = {
    backendProcess: null,
    frontendProcess: null,
    frontendWebServer: null,
    electronWindow: null,
  };

  return {
    CONSTANTS,
    LOGGERS,
    UTILS,
    INSTANCES,
  };
}
