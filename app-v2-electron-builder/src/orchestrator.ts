import { BrowserWindow } from "electron";
import type { OrchestratorDeps } from "./orchestrator.deps";
import { WebServer } from "./lib/web-server";

import type { EnvVarsInput as FrontendProdEnvVars } from '../../app-v2/frontend-react/src/constants/input-env-vars.type.d.ts';

export type OrchestratorInitProps = {
  DEPS: OrchestratorDeps;
  electronApp: Electron.App;
};

export class Orchestrator {
  private DEPS: OrchestratorInitProps['DEPS'];
  private electronApp: OrchestratorInitProps['electronApp'];

  constructor({
    DEPS,
    electronApp
  }: OrchestratorInitProps) {
    this.DEPS = DEPS;
    this.electronApp = electronApp;
  }

  /** 
   * Main public function of this class.  
   * You must call this function on `electronApp.on('ready')`  
   * This will initalize all `electronApp` event handlers callback
   * */
  async initializeElectronApp() {
    const { electronApp } = this;

    await this.onAppInit();

    electronApp.on('activate', async () => {
      await this.onAppActivate();
    });

    electronApp.on('window-all-closed', async () => {
      await this.onAppStop();
      if (this.DEPS.CONSTANTS.OS.platform !== 'darwin') {
        electronApp.quit();
      }
    });

    electronApp.on('before-quit', async () => {
      await this.onAppStop();
    });

  }

  /** Callback of `app.on('ready')` */
  private async onAppInit() {
    const { LOGGERS, CONSTANTS, UTILS } = this.DEPS;

    LOGGERS.ORC.log('🚀 onAppInit - START');
    LOGGERS.ORC.log('\nCONSTANTS:\n' + JSON.stringify(CONSTANTS, null, 2));
    LOGGERS.ORC.log(`App is in "${CONSTANTS.ENV_TYPE.toUpperCase()}" mode`);

    await this.startBackendProcess();
    await UTILS.OS.waitForService(CONSTANTS.SERVERS.BACKEND_URL);

    await this.startFrontendProcess();
    await UTILS.OS.waitForService(CONSTANTS.SERVERS.FRONTEND_URL);

    await this.createElectronWindow();

    LOGGERS.ORC.log('🚀 onAppInit - END ✅');

  }

  /** Callback of `app.on('window-all-closed')` */
  private async onAppStop() {
    const { LOGGERS, UTILS, INSTANCES } = this.DEPS;

    LOGGERS.ORC.log('🚀 onAppStop - START');

    LOGGERS.ORC.log('- Stopping Backend (Python + FastAPI)...');
    UTILS.SHELL.killProcess(INSTANCES.backendProcess);

    LOGGERS.ORC.log('- Stopping Frontend (React)...');
    UTILS.SHELL.killProcess(INSTANCES.frontendProcess);
    INSTANCES.frontendWebServer?.kill();

    LOGGERS.ORC.log('🚀 onAppStop - END ✅');
  }

  /** Callback of `app.on('activate')` */
  private async onAppActivate() {
    if (!this.DEPS.INSTANCES.electronWindow) {
      await this.createElectronWindow();
    }
  }

  /** Start Backend process (backend python) */
  private async startBackendProcess() {
    const { CONSTANTS, LOGGERS, UTILS, INSTANCES } = this.DEPS;

    LOGGERS.ORC.log('🚀 startBackendProcess - START');

    // in DEV and in PROD, 

    // 1. launch the backend server (python fastapi webserver)
    // this server will run in background and will be accessed by the react frontend
    // the backend code is bundled in the app (by electron-builder)
    // NOTE: the constants are different for dev and prod
    LOGGERS.ORC.log(`- Starting Backend (Python + FastAPI) with python. Port: ${CONSTANTS.SERVERS.BACKEND_PORT}`);
    INSTANCES.backendProcess = UTILS.SHELL.launchProcess(
      CONSTANTS.PATHS.BACKEND_VENV_BIN_PYTHON_PATH,
      ["main.py"],
      {
        cwd: CONSTANTS.PATHS.BACKEND_DIR_PATH,
        stdio: 'pipe',
        env: {
          BACKEND_PORT: CONSTANTS.SERVERS.BACKEND_PORT.toString(),
          FRONTEND_PORT: CONSTANTS.SERVERS.FRONTEND_PORT.toString(),
          // STATIC_DIR_TO_SERVE_PATH: CONSTANTS.PATHS.FRONTEND_DIR_PATH,
          LOG_LEVEL: "info"
        }
      }
    );
    INSTANCES.backendProcess.on('error', (err) => {
      LOGGERS.BE.error('❌ Failed to start backend:', err);
    });
    INSTANCES.backendProcess.stdout?.on('data', (data: Buffer) => {
      LOGGERS.BE.log(data.toString('utf-8').trimEnd());
    });
    INSTANCES.backendProcess.stderr?.on('data', (data: Buffer) => {
      LOGGERS.BE.error(data.toString('utf-8').trimEnd());
    });

    LOGGERS.ORC.log('🚀 startBackendProcess - END ✅');

  }

  /** Start Frontend process (frontend react) */
  private async startFrontendProcess() {
    const { CONSTANTS, LOGGERS, UTILS, INSTANCES } = this.DEPS;

    LOGGERS.ORC.log('🚀 startFrontendProcess - START');

    // in DEV
    if (CONSTANTS.ENV_TYPE === 'dev') {
      // 1. run dev servr of vite directly
      LOGGERS.ORC.log('- Starting Frontend (React) with Vite...');
      INSTANCES.frontendProcess = UTILS.SHELL.launchProcess(
        'pnpm', ['run', 'dev'],
        {
          cwd: CONSTANTS.PATHS.FRONTEND_DIR_PATH,
          stdio: 'pipe',
        }
      );
      INSTANCES.frontendProcess.on('error', (err) => {
        LOGGERS.FE.error(err);
      });
      INSTANCES.frontendProcess.stdout?.on('data', (data: Buffer) => {
        LOGGERS.FE.log(data.toString('utf-8').trimEnd());
      });
      INSTANCES.frontendProcess.stderr?.on('data', (data: Buffer) => {
        LOGGERS.FE.error(data.toString('utf-8').trimEnd());
      });

    }
    // in PROD
    else {

      // 1. add constants needed by the frontend by replacing the index.html file <script> tag
      // example of th tag content
      /*
      // FRONTEND_CONFIG_START 
      window.FRONTEND_SAFE_ENV_VARS = {
        BACKEND_HTTP_API_URL: "http://localhost:8000",
        BACKEND_WS_API_URL: "ws://localhost:8000",
      }
      // FRONTEND_CONFIG_END 
      */
      LOGGERS.ORC.log('- Adding constants to Frontend index.html (window.FRONTEND_SAFE_ENV_VARS)...');
      await UTILS.DISK.replaceTextInFile({
        filePath: CONSTANTS.PATHS.FRONTEND_INDEX_HTML_PATH,
        toReplaceRegexp: /\/\/ FRONTEND_CONFIG_START(.|\n)*\/\/ FRONTEND_CONFIG_END/g,
        replaceWithText: `
        // FRONTEND_CONFIG_START 
        // Following values:
        // - are injected by ELECTRON-MAIN code at app launch (before serving frontnd spa)
        // - are PROD only
        window.FRONTEND_SAFE_ENV_VARS = ${JSON.stringify({
          BACKEND_HTTP_API_URL: CONSTANTS.SERVERS.BACKEND_URL,
          BACKEND_WS_API_URL: `ws://localhost:${CONSTANTS.SERVERS.BACKEND_PORT}`,
          APP_VERSION: CONSTANTS.APP_GENERAL.version,
          FRONTEND_APP_MODE: "PROD",
        } satisfies FrontendProdEnvVars)}
        // FRONTEND_CONFIG_END
      `,
      });

      // 2. start a webserver to serve the static react spa
      // that must be built (by vite) and then bundled in the app bundle (by electron-builder)
      LOGGERS.ORC.log(`- Starting Frontend (React) with Node.js Webserver. Port: ${CONSTANTS.SERVERS.FRONTEND_PORT}`);
      INSTANCES.frontendWebServer = new WebServer({
        dirPathToServe: CONSTANTS.PATHS.FRONTEND_DIR_PATH,
        port: CONSTANTS.SERVERS.FRONTEND_PORT,
        logger: LOGGERS.FE,
      });
      INSTANCES.frontendWebServer.launch();
    }

    LOGGERS.ORC.log('🚀 startFrontendProcess - END ✅');

  }

  /** Create Electron window and navigate to the frontend */
  private async createElectronWindow() {
    const { CONSTANTS, INSTANCES, LOGGERS } = this.DEPS;

    LOGGERS.ORC.log('🚀 createElectronWindow - START');

    // 1. create electron window
    LOGGERS.ORC.log('- Creating Electron window...');
    INSTANCES.electronWindow = new BrowserWindow({
      width: CONSTANTS.ELECTRON_WINDOW.WIDTH,
      height: CONSTANTS.ELECTRON_WINDOW.HEIGHT,
      webPreferences: {
        nodeIntegration: false,
        contextIsolation: true,
        // enableRemoteModule: false,
      },
    });
    INSTANCES.electronWindow.on('closed', () => {
      INSTANCES.electronWindow = null;
    });

    // 2. navigate to the frontend spa index.html
    LOGGERS.ORC.log(`- Navigating to Frontend at ${CONSTANTS.SERVERS.FRONTEND_URL}`);
    INSTANCES.electronWindow.loadURL(CONSTANTS.SERVERS.FRONTEND_URL);

    // 3. open dev tools
    if (CONSTANTS.ENV_TYPE === 'dev') {
      LOGGERS.ORC.log('- Enabling dev tools...');
      INSTANCES.electronWindow.webContents.openDevTools();
    }

    LOGGERS.ORC.log('🚀 createElectronWindow - END ✅');
  }
}