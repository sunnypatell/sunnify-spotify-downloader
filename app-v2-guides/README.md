# App Architecture

- **Backend** Python + FastAPI
- **Frontend** React + Vite

## App Modes

### Development

In dev, we launch the backend (python) and the frontend (react+vite) in 2 separate shell processes, and treat the workflow like a regular website.

```bash
# backend
cd app-v2
cd backend-python
source .venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt # only first time
cp .env.example .env # only first time
python main.py

# API at: http://localhost:8000
# API Docs at: http://localhost:8000/docs

```

```bash
# frontend
cd app-v2
cd frontend-react
pnpm run dev

# UI at: http://localhost:3000
```

**How to do other common dev tasks?**

See the following guides:
- [app-v2/backend-python/README.md](../app-v2//backend-python/README.md)
- [app-v2/frontend-react/README.md](../app-v2//frontend-react/README.md)

### Production

In production, the app is an electron app bundled with electron-builder.  
Bundled means that the full app is packaged in a single file:
- Mac: `.app` bundle
- Windows: `.exe` file
- Linux: `.AppImage` file

Electron apps requires these phases:
- **BUNDLE** the app is bundled with electron-builder that outputs executable artifacts. This happens in the developer machine (or cloud build machine)
- **DISTRIBUTION** the executable is then distributed in a single file to users
- **LAUNCH** the user launch the app by running the executable. This happens in the user machine.


**BUNDLE**  

To trigger the bundle phase, run:
```bash
cd app-v2-electron-builder
npm i
npm run pack
```
that
- **compile electron code**  
generate the compiled js for the `electron` codebase from `app-v2-electron-builder/src` to `app-v2-electron-builder/dist-electron-main`, by running `npm run electron-main:build`, that output files in `app-v2/electron-builder/dist-electron-main`
- **compile frontend SPA code**  
generate the static SPA of the frontend with `pnpm build`, that output files in `app-v2/frontend-react/dist`
- **copy files to the bundle**  
  - copy backend `app-v2/backend-python` at `app/dist-backend`
  - copy electron `app-v2-electron-builder/dist-electron-main` at `app/dist-electron-main`
  - copy frontend `app-v2/frontend-react/dist` at `app/dist-frontend`
  - copy other files, as defined in `electron-builder.yml` by `files` and `extraResources` properties. These files are needed by the `electron` code.


**DISTRIBUTION**  

Choose your method for distributing the app bundle, like:
- usb drive
- cloud storage
- email
- ...


**LAUNCH**  

The user launch the app by running the executable.
The executable launch the `electron` code, that:
- **Generate 2 service ports**  
`BACKEND_PORT` and `FRONTEND_PORT`
- **Launch backend server**  
using node.js child process to run the equivalent of running 
```bash
BACKEND_PORT=1234 FRONTEND_PORT=4321 python main.py
```
- **Launch frontend app**  
by replacing a piece of the HTML code of `index.html` to "pass" env vars to the frontend app by augmenting the window object `window.FRONTEND_SAFE_ENV_VARS`.  
Then using node.js http module to serve static files of the frontend SPA at port `FRONTEND_PORT`
- **Launch chromium browser window**  
that navigate to the frontend URL `http://localhost:FRONTEND_PORT`

