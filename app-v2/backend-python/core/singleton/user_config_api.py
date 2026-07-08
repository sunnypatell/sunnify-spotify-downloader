from core.classes.data.user_config_api import UserConfigApi, UserConfigReaderApi
from core.singleton.app_config import appConfig

# init singletons
userConfigApi = UserConfigApi(
  config_file=appConfig.runtime.user_config_file_path
)
userConfigReaderApi = UserConfigReaderApi(
  userConfigApi=userConfigApi
)