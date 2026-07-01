import { app, BrowserWindow } from 'electron';
import { CONSTANTS } from './constants';
import { LOGGERS, UTILS } from './main.deps';


/** child process of backend server launched */
let backendProcess: ReturnType<typeof UTILS.SHELL.launchProcess> | null = null;
/** child process of frontend server launched */
let frontendProcess: ReturnType<typeof UTILS.SHELL.launchProcess> | null = null;
/** instance of Electron WebView (browser window) */
let electronWindow: BrowserWindow | null = null;

function startBackendProcess() {
  LOGGERS.ORC.log('🚀 Starting Backend (Python + FastAPI)...');

  // here we launch the backend server of thap (python fastapi webserver)
  // this server will run in background
  backendProcess = UTILS.SHELL.launchProcess(
    CONSTANTS.PATHS.BACKEND_VENV_BIN_PYTHON_PATH,
    ["main.py"],
    {
      cwd: CONSTANTS.PATHS.BACKEND_DIR_PATH,
      stdio: 'pipe',
    }
  );

  backendProcess.on('error', (err) => {
    LOGGERS.BE.error('❌ Failed to start backend:', err);
  });
  backendProcess.stdout?.on('data', (data: Buffer) => {
    LOGGERS.BE.log(data.toString('utf-8').trimEnd());
  });
  backendProcess.stderr?.on('data', (data: Buffer) => {
    LOGGERS.BE.error(data.toString('utf-8').trimEnd());
  });
}

function startFrontendProcess() {
  LOGGERS.ORC.log('🚀 Starting Frontend (React)...');

  if (CONSTANTS.ENV_TYPE === 'dev') {
    frontendProcess = UTILS.SHELL.launchProcess(
      'npm', ['run', 'dev'],
      {
        cwd: CONSTANTS.PATHS.FRONTEND_DIR_PATH,
        stdio: 'pipe',
      }
    );
  }
  else {
    // here we launch a web server using "serve" (node module) that serve the compiled frontend SPA
    // then the electron main window will navigate to spa index.html
    // this server will run in background
    frontendProcess = UTILS.SHELL.launchProcess(
      CONSTANTS.PATHS.ELECTRON_NODE_MODULES_SERVE_BIN_PATH,// serve node module bin
      [
        'dist-frontend/client', // which directory to serve (all files in this directory will be served)
        "-p", String(CONSTANTS.SERVERS.FRONTEND_PORT), // port
        "-s", "", // (required for SPA) serve index.html for all requests pathname not matching a file
      ],
      {
        cwd: CONSTANTS.PATHS.APP,
        stdio: 'pipe',
      }
    );
  }

  frontendProcess?.on('error', (err) => {
    LOGGERS.FE.error(err);
  });
  frontendProcess?.stdout?.on('data', (data: Buffer) => {
    LOGGERS.FE.log(data.toString('utf-8').trimEnd());
  });
  frontendProcess?.stderr?.on('data', (data: Buffer) => {
    LOGGERS.FE.error(data.toString('utf-8').trimEnd());
  });
}

async function createElectronWindow() {
  electronWindow = new BrowserWindow({
    width: CONSTANTS.ELECTRON_WINDOW.WIDTH,
    height: CONSTANTS.ELECTRON_WINDOW.HEIGHT,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      // enableRemoteModule: false,
    },
  });

  // navigate to the frontend spa index.html
  electronWindow.loadURL(CONSTANTS.SERVERS.FRONTEND_URL);

  electronWindow.webContents.openDevTools();
  electronWindow.on('closed', () => {
    electronWindow = null;
  });
}

async function run() {

  LOGGERS.ORC.log('🚀 Starting Orchestration...');
  LOGGERS.ORC.log('CONSTANTS:');
  LOGGERS.ORC.log(JSON.stringify(CONSTANTS, null, 2));

  startBackendProcess();
  startFrontendProcess();

  await UTILS.OS.waitForService(CONSTANTS.SERVERS.BACKEND_URL);
  await UTILS.OS.waitForService(CONSTANTS.SERVERS.FRONTEND_URL);

  await createElectronWindow();

  LOGGERS.ORC.log('✅ Orchestration completed.');
}

app.on('ready', run);
app.on('window-all-closed', () => {
  UTILS.SHELL.killProcess(backendProcess);
  UTILS.SHELL.killProcess(frontendProcess);
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
app.on('activate', () => {
  if (!electronWindow) {
    createElectronWindow();
  }
});
app.on('before-quit', () => {
  UTILS.SHELL.killProcess(backendProcess);
  UTILS.SHELL.killProcess(frontendProcess);
});