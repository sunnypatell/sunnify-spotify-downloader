from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from models.new import WsBackendEventPayloadTypeMessage
from core.singleton.logger import logger
from core.singleton.websocket_event_emitter import webSocketEventEmitter
from core.singleton.websocket_active_connections import webSocketActiveConnections

router = APIRouter(prefix="/ws", tags=["ws"])

# ============================================================================
# WebSocket for real-time updates
# ============================================================================

@router.websocket("/entry-point")
async def webSocketEntryPoint(websocket: WebSocket):
  """
  WebSocket endpoint use to push real-time updates from backend to frontend.
  We push various message types to frontend.
  """
  # accept connection
  await websocket.accept()
  logger.info("/ws/entry-point - Connection accepted")
  
  # set connection to singleton instance
  webSocketActiveConnections.appendConnection(websocket)
  
  # send a welcome message
  await webSocketEventEmitter.emit(
    eventPayload=WsBackendEventPayloadTypeMessage(
      text="Hello from backend!"
    )
  )
  
  # loop for ever
  tickCount = 0
  while True:
    try:
      tickCount += 1
      logger.info(f"/ws/entry-point - While loop tick {tickCount}")
      await websocket.receive()
    except WebSocketDisconnect:
      logger.info("/ws/entry-point - Connection closed from client (WebSocketDisconnect)")
      webSocketActiveConnections.removeConnection(websocket)
      break
    except Exception as e:
      logger.info("/ws/entry-point - Unexpected error (Exception). Closing connection!")
      webSocketActiveConnections.removeConnection(websocket)
      break
    
  logger.info("/ws/entry-point - While loop ended")
