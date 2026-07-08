from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from core.singleton.logger import logger
from core.singleton.app_config import appConfig
from core.singleton.native_deps_checker import nativeDepsChecker
from core.singleton.websocket_active_connections import webSocketActiveConnections

# Import API Routers
from routers import (
  health,
  ws,
  demo,
  playlist,
  settings,
  utils,
)

# ============================================================================
# Setup API
# ============================================================================

def createFastApiApp():

  logger.info("")
  logger.info("Initializing Backend...")
  
  logger.info(f"APP CONFIG - Environment variables: \n{appConfig.envVars.model_dump_json()}")
  logger.info(f"APP CONFIG - Runtime variables: \n{appConfig.runtime.dump()}")
  
  logger.info("Create user config file directory if necessary...")
  appConfig.runtime.user_config_dir_path.mkdir(parents=True, exist_ok=True)
  
  logger.info("Checking presence of native dependencies...")
  nativeDepsChecker.checkAllDepsPresenceAndDownloadThemIfMissing()
  
  # define FastAPI lifecycle hooks
  @asynccontextmanager
  async def fastApiAppLifespanHandler(app: FastAPI):
    # startup (before server starts)
    logger.info("FastAPI - Lifecycle Hook - Before Server start")
    
    logger.info(f"FastAPI server will start at http://localhost:{str(appConfig.envVars.BACKEND_PORT)}\n")
    
    # shutdown (after server stops)
    yield
    logger.info("FastAPI - Lifecycle Hook - Before Server Stop")
    
    logger.info("Shutting down WebSocket connections...")
    await webSocketActiveConnections.shutdownAllConnections()
    
    logger.info("Cleanup done")

  # create FastAPI instance
  logger.info("FastAPI APP: Creating FastAPI instance...")
  app = FastAPI(
    lifespan=fastApiAppLifespanHandler,
    title="SpotiDisk API",
    description="Spotify Playlist Downloader (audio source YouTube)",
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
  )

  # add CORS middleware
  logger.info("FastAPI APP: Adding CORS middleware...")
  app.add_middleware(
    CORSMiddleware,
    allow_origins=appConfig.runtime.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
  )

  # register API endpoints
  logger.info("FastAPI APP: Registering API endpoints...")
  for router in [
    health.router,
    ws.router,
    demo.router,
    playlist.router,
    settings.router,
    utils.router,
  ]:
    logger.info(f"FastAPI APP: Registering router: {router.prefix or '/'}")
    app.include_router(router)
  
  # register /static/** endpoint (to serve the static files)
  if not appConfig.envVars.STATIC_DIR_TO_SERVE_PATH:
    logger.info("FastAPI APP: Skip static files serving, because STATIC_DIR_TO_SERVE_PATH is not set...")
  else:
    logger.info("FastAPI APP: Register that /static/** will serve static files...")
    app.mount(
      "/static",
      StaticFiles(
        directory=appConfig.envVars.STATIC_DIR_TO_SERVE_PATH,
        html=True,
      ),
      name="static-files",
    )
  
  return app


# ============================================================================
# Run
# ============================================================================

app = createFastApiApp()

if __name__ == "__main__":
  logger.info("Serving Backend with Uvicorn...")
  import uvicorn
  uvicorn.run(
    "main:app",
    host="127.0.0.1",
    port=appConfigStatic.backend_port,
    reload=appConfigStatic.debug,
    log_level=appConfigStatic.log_level,
  )
  logger.info("Backend stopped")
