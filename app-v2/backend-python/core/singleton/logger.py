import logging
from core.singleton.app_config import appConfigStatic

# init
logging.basicConfig(
  level=appConfigStatic.log_level.upper(),
)
logger = logging.getLogger(name="main")
