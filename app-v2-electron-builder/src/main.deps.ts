import { CONSTANTS } from "./constants";
import { Logger, LoggerTransportConsole, LoggerTransportFile, type LoggerTransport } from "./utils/logger";
import { UtilsOs } from "./utils/os";
import { utilsShell } from "./utils/shell";

const LOGGER_TRANSPORTS: LoggerTransport[] = [
  new LoggerTransportConsole(),
  new LoggerTransportFile(CONSTANTS.PATHS.LOG_FILE_PATH),
];

export const LOGGERS = {
  ORC: new Logger({ key: 'ORCHESTRATOR', color: 'blue', transports: LOGGER_TRANSPORTS }),
  BE: new Logger({ key: 'BACKEND', color: 'green', transports: LOGGER_TRANSPORTS }),
  FE: new Logger({ key: 'FRONTEND', color: 'yellow', transports: LOGGER_TRANSPORTS }),
};

export const UTILS = {
  OS: new UtilsOs({ logger: LOGGERS.ORC }),
  SHELL: utilsShell,
};