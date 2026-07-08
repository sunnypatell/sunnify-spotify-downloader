from core.classes.config.app_config import (
  EnvironmentVariables,
  AppConfigRuntime, 
  AppConfig, 
)

# init singletons
envVars=EnvironmentVariables() # pyright: ignore[reportCallIssue]
appConfigRuntime=AppConfigRuntime(envVars=envVars)
appConfig = AppConfig(
  envVars=envVars,
  runtime=appConfigRuntime,
)
