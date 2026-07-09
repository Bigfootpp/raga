import asyncio

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, WebSocketException

from gateway.dispatcher import Dispatcher
from pydantic import ValidationError
from shared.frames import Action, ErrorEvent, ErrorMessage, to_action

app = FastAPI()

@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Raga is online"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    dispatcher = Dispatcher()

    async def handle_error(e: Exception) -> bool:
        print(f"Error: ({e.__class__.__name__}): {e}")
        match e:
            case ValidationError():
                try:
                    await websocket.send_json(ErrorEvent(message=ErrorMessage.INVALID_FORMAT, details=e.errors()).to_dict())
                except Exception:
                    return True
                return False
            case WebSocketException() | WebSocketDisconnect():
                return True
            case Exception():
                try:
                    await websocket.send_json(ErrorEvent(message=ErrorMessage.INTERNAL_ERROR).to_dict())
                except Exception:
                    return True
                return False

    async def handle(action_json: str):
        try:
            action: Action = to_action(action_json)
            
            async for event in dispatcher.dispatch(action=action):
                await websocket.send_json(event.to_dict())

        except Exception as e:
            await handle_error(e=e)
            return
    
    while True:
        try:
            action: str = await websocket.receive_text()
            asyncio.create_task(handle(action_json=action))
        except Exception as e:
            need_break = await handle_error(e=e)
            if need_break:
                break
    
    try:
        await websocket.close()
    except Exception:
        pass