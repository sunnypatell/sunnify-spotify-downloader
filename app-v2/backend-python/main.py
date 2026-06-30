from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from core.singleton.logger import logger
from core.singleton.app_config import appConfigStatic
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

logger.info("Initializing Backend...")

# define lifecycle hooks
@asynccontextmanager
async def fastApiAppLifespanHandler(app: FastAPI):
  # startup (before server starts)
  port=appConfigStatic.backend_port
  logger.info("FastAPI server started at http://127.0.0.1:" + str(port))
  # shutdown (after server stops)
  yield
  await webSocketActiveConnections.shutdownAllConnections()


# api
logger.info("API Router: Creating FastAPI instance...")
app = FastAPI(
  lifespan=fastApiAppLifespanHandler,
  title="Sunnify API",
  description="Spotify & YouTube music downloader",
  version="2.1.0",
  docs_url="/docs",
  openapi_url="/openapi.json",
)

# api CORS middleware
logger.info("API Router: Adding CORS middleware...")
app.add_middleware(
  CORSMiddleware,
  allow_origins=appConfigStatic.cors_origins,
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)


# register API endpoints
logger.info("API Router: Registering API endpoints...")
app.include_router(health.router)
app.include_router(ws.router)
app.include_router(demo.router)
app.include_router(playlist.router)
app.include_router(settings.router)
app.include_router(utils.router)


# ============================================================================
# Run
# ============================================================================

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
