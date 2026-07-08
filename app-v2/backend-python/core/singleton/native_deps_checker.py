from core.classes.utils.utils_native_deps_checker import UtilsNativeDepsChecker
from core.singleton.app_config import appConfig

nativeDepsChecker = UtilsNativeDepsChecker(
  location1LocalBinFolderPath=str(appConfig.runtime.binaries_path)
)