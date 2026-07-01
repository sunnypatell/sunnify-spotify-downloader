import path from "node:path";
import { app } from "electron";
import config from "../config.json";
import { utilsString } from "./utils/string";

const IS_DEV = process.env.NODE_ENV === 'development' || !app.isPackaged;

export const CONSTANTS = (() => {

  // Development: usa i percorsi reali
  // Production: backend/frontend è dentro il bundle dell'app

  if (IS_DEV) {
    return {
      ENV_TYPE: 'dev',
      PATHS: {
        CWD: process.cwd(),
        APP: undefined,
        BACKEND_DIR_PATH: path.join(__dirname, '../../app-v2/backend-python'),
        BACKEND_VENV_ACTIVATE_PATH: path.join(__dirname, '../../app-v2/backend-python/.venv/bin/activate'),
        BACKEND_VENV_BIN_PYTHON_PATH: path.join(__dirname, '../../app-v2/backend-python/.venv/bin/python'),
        FRONTEND_DIR_PATH: path.join(__dirname, '../../app-v2/frontend-react'),
        LOG_FILE_PATH: path.join(__dirname, `../logs/${new Date().toISOString().slice(0, 10)}.txt`),
      },
      SERVERS: {
        BACKEND_PORT: config.backend.dev.port,
        BACKEND_URL: `http://localhost:${config.backend.dev.port}`,
        FRONTEND_PORT: config.frontend.dev.port,
        FRONTEND_URL: `http://localhost:${config.frontend.dev.port}`,
      },
      ELECTRON_WINDOW: {
        WIDTH: config.frontend.base.window.width,
        HEIGHT: config.frontend.base.window.height,
      }
    } as const;
  }

  return {
    ENV_TYPE: 'prod',
    PATHS: {
      CWD: process.cwd(),
      ELECTRON_BIN_NODE_PATH: process.execPath,
      // ELECTRON_NODE_MODULES_DIR_PATH: path.join(process.resourcesPath, 'app/node_modules'),
      ELECTRON_NODE_MODULES_SERVE_BIN_PATH: path.join(process.resourcesPath, 'app/node_modules/.bin/serve'),
      ELECTRON_NODE_MODULES_SERVE_JS_PATH: path.join(process.resourcesPath, 'app/node_modules/serve'),
      APP: path.join(process.resourcesPath, 'app'),
      BACKEND_DIR_PATH: path.join(process.resourcesPath, 'app/dist-backend'),
      BACKEND_VENV_ACTIVATE_PATH: path.join(process.resourcesPath, 'app/dist-backend/.venv/bin/activate'),
      BACKEND_VENV_BIN_PYTHON_PATH: path.join(process.resourcesPath, 'app/dist-backend/.venv/bin/python'),
      FRONTEND_DIR_PATH: path.join(process.resourcesPath, 'app/dist-frontend'),
      // LOG_FILE_PATH: path.join(process.resourcesPath, `app/logs/${new Date().toISOString().slice(0, 10)}.txt`),
      LOG_FILE_PATH: `/Users/jacopo/Desktop/LOGS/log--${utilsString.slugify(new Date().toISOString())}.txt`,
      // FRONTEND_INDEX_HTML_PATH: path.join(process.resourcesPath, 'app/dist-frontend/client/index.html'),
    },
    SERVERS: {
      BACKEND_PORT: config.backend.prod.port,
      BACKEND_URL: `http://localhost:${config.backend.prod.port}`,
      FRONTEND_PORT: config.frontend.prod.port,
      FRONTEND_URL: `http://localhost:${config.frontend.prod.port}`,
    },
    ELECTRON_WINDOW: {
      WIDTH: config.frontend.base.window.width,
      HEIGHT: config.frontend.base.window.height,
    }
  } as const;

})();
