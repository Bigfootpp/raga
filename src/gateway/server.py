import asyncio

from fastapi import FastAPI, WebSocket, WebSocketException

from gateway.dispatcher import Dispatcher
from pydantic import ValidationError
from utils.messages import Action, to_action

app = FastAPI()

@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Raga is online"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    dispatcher = Dispatcher()

    async def handle_error(e: Exception):
        print(e.__class__)
        print(e)
        match e:
            case ValidationError():
                await websocket.send_json({
                    "type": "error",
                    "data": {
                        "message": "Invalid format",
                        "details": e.errors()
                    }
                })
                return
            case WebSocketException():
                return
            case Exception():
                await websocket.send_json({
                    "type": "error",
                    "data": {
                        "message": "Une erreur interne est survenue durant le traitement."
                    }
                })
                return

    async def handle(action_json: str):
        try:
            action: Action = to_action(action_json)
            
            async for event in dispatcher.dispatch(message=action):
                await websocket.send_json(event.to_dict())

        except Exception as e:
            await handle_error(e=e)
            return
    
    while True:
        try:
            action: str = await websocket.receive_text()
            asyncio.create_task(handle(action_json=action))
        except Exception as e:
            await handle_error(e=e)