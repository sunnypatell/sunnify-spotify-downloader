import path from "node:path";
import { app } from "electron";
import config from "../config.json";
import { utilsOs } from "./utils/os";
import { utilsPath } from "./utils/path";

export async function createConstants() {

  const IS_DEV = process.env.NODE_ENV === 'development' || !app.isPackaged;

  // Development: usa i percorsi reali
  // Production: backend/frontend è dentro il bundle dell'app

  // dev
  if (IS_DEV) {
    return {
      ENV_TYPE: 'dev',
      OS: utilsOs.getOSInfo(),
      ELECTRON_RUNTIME: {
        VERSIONS: process.versions.node
      },
      PATHS: {
        USER_HOME_PATH: utilsPath.getUserHomeDir(),
        USER_DESKTOP_PATH: utilsPath.getUserDesktopDir(),
        CWD: utilsPath.getCWD(),
        APP: undefined,
        BACKEND_DIR_PATH: path.join(__dirname, '../../app-v2/backend-python'),
        BACKEND_VENV_ACTIVATE_PATH: path.join(__dirname, '../../app-v2/backend-python/.venv/bin/activate'),
        BACKEND_VENV_BIN_PYTHON_PATH: path.join(__dirname, '../../app-v2/backend-python/.venv/bin/python'),
        FRONTEND_DIR_PATH: path.join(__dirname, '../../app-v2/frontend-react'),
        LOG_FILE_PATH: path.join(utilsPath.getUserDesktopDir(), `/SPOTIDISK-LOGS/log--${new Date().toISOString()}.txt`),
        LOG_FILE_PATH_2: path.join(utilsPath.getUserHomeDir(), `.spotidisk/logs/${new Date().toISOString()}.txt`),
      },
      SERVERS: {
        BACKEND_PORT: 8000,
        BACKEND_URL: `http://localhost:${8000}`,
        FRONTEND_PORT: 3000,
        FRONTEND_URL: `http://localhost:${3000}`,
      },
      APP_GENERAL: config.general,
      ELECTRON_WINDOW: {
        WIDTH: config.electronWindow.base.window.width,
        HEIGHT: config.electronWindow.base.window.height,
      }
    } as const;
  }

  // prod
  const RANDOM_PORT_1 = await utilsOs.getFreePort();
  const RANDOM_PORT_2 = await utilsOs.getFreePort();

  return {
    ENV_TYPE: 'prod',
    OS: utilsOs.getOSInfo(),
    ELECTRON_RUNTIME: {
      VERSIONS: process.versions.node
    },
    PATHS: {
      USER_HOME_PATH: utilsPath.getUserHomeDir(),
      USER_DESKTOP_PATH: utilsPath.getUserDesktopDir(),
      CWD: utilsPath.getCWD(),
      APP: path.join(process.resourcesPath, 'app'),
      BACKEND_DIR_PATH: path.join(process.resourcesPath, 'app/dist-backend'),
      BACKEND_VENV_ACTIVATE_PATH: path.join(process.resourcesPath, 'app/dist-backend/.venv/bin/activate'),
      BACKEND_VENV_BIN_PYTHON_PATH: path.join(process.resourcesPath, 'app/dist-backend/.venv/bin/python'),
      FRONTEND_DIR_PATH: path.join(process.resourcesPath, 'app/dist-frontend/client'),
      FRONTEND_INDEX_HTML_PATH: path.join(process.resourcesPath, 'app/dist-frontend/client/index.html'),
      LOG_FILE_PATH: path.join(utilsPath.getUserDesktopDir(), `/SPOTIDISK-LOGS/log--${new Date().toISOString()}.txt`),
      LOG_FILE_PATH_2: path.join(utilsPath.getUserHomeDir(), `.spotidisk/logs/${new Date().toISOString()}.txt`),
    },
    SERVERS: {
      BACKEND_PORT: RANDOM_PORT_1,
      BACKEND_URL: `http://localhost:${RANDOM_PORT_1}`,
      FRONTEND_PORT: RANDOM_PORT_2,
      FRONTEND_URL: `http://localhost:${RANDOM_PORT_2}`,
    },
    APP_GENERAL: config.general,
    ELECTRON_WINDOW: {
      WIDTH: config.electronWindow.base.window.width,
      HEIGHT: config.electronWindow.base.window.height,
    }
  } as const;
}