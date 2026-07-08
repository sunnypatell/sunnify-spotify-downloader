export type EnvVarsInput = {
  /** The URL of the backend server for the HTTP API @example "http://127.0.0.1:8000" */
  BACKEND_HTTP_API_URL: string,
  /** The URL of the backend server for the WebSocket API @example "ws://127.0.0.1:8000" */
  BACKEND_WS_API_URL: string,
  /** The version of the app @example "0.0.1" */
  APP_VERSION: string,
  /** The mode of the app @example "DEV" | "PROD" */
  FRONTEND_APP_MODE: 'DEV' | 'PROD',
};