from typing import Optional

from fastapi import FastAPI, WebSocket

from gateway.dispatcher import Dispatcher
from agent_core.streaming import Event

app = FastAPI()

@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Raga is online"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    dispatcher = Dispatcher()

    try:
        while True:
            message: dict = await websocket.receive_json()
            message_type: Optional[str] = message.get("type")
            data: Optional[dict] = message.get("data")

            if message_type and data:
                client_event = Event(type=message_type, data=data)
                async for event in dispatcher.dispatch(message=client_event):
                    await websocket.send_json(event.to_dict)

            
    except Exception:
        pass