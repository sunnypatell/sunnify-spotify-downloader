from core.classes.data.user_config_api import UserConfigApi, UserConfigReaderApi
from core.singleton.app_config import appConfigRuntime

# init singletons
userConfigApi = UserConfigApi(
  config_file=appConfigRuntime.user_config_file_path
)
userConfigReaderApi = UserConfigReaderApi(
  userConfigApi=userConfigApi
)