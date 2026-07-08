import logging
from core.singleton.app_config import appConfig

# init
logging.basicConfig(
  level=appConfig.envVars.LOG_LEVEL.upper(),
)
logger = logging.getLogger(name="main")
