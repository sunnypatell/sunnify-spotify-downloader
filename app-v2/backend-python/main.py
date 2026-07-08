from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from core.singleton.logger import logger
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
  
# register API endpoints
logger.info("API Router: Registering API endpoints...")
app.include_router(health.router)
app.include_router(ws.router)
app.include_router(demo.router)
app.include_router(playlist.router)
app.include_router(settings.router)
app.include_router(utils.router)

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
