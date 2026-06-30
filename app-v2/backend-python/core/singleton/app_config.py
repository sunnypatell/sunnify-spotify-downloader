from core.classes.config.app_config import AppConfigStatic, AppConfigRuntime, AppConfig

# init singletons
appConfigStatic = AppConfigStatic()
appConfigRuntime = AppConfigRuntime()
appConfig = AppConfig(
  static=appConfigStatic,
  runtime=appConfigRuntime
)
