from models.new import WsBackendEvent, WsBackendEventPayload
from core.singleton.logger import logger
from core.classes.notifications.websocket_active_connections import WebSocketActiveConnections
from core.classes.utils.utils_time import UtilsTime

class WebSocketEventEmitter:
  """Object that emits events to connected websockets clients"""
  def __init__(
    self,
    webSocketActiveConnections: WebSocketActiveConnections
  ):
    self.webSocketActiveConnections: WebSocketActiveConnections = webSocketActiveConnections
    
  async def emit(self, eventPayload: WsBackendEventPayload):
    connections = self.webSocketActiveConnections.getActiveConnections()
    
    # send event
    for ws in connections:
      logger.debug(f"WebSocketEventEmitter - emit - sending event to client")
      try:
        event = WsBackendEvent(
          dateTimeISO=UtilsTime.getCurrentDateTimeIso(),
          payload=eventPayload
        )
        await ws.send_json(event.model_dump())
        logger.debug(f"WebSocketEventEmitter - emit - event sent: {event}")
      except Exception as e:
        logger.error(f"WebSocketEventEmitter - emit - error sending event: {e}")