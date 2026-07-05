import asyncio
import json
from typing import Optional

import websockets
from websockets.asyncio.client import ClientConnection

from utils.frames import (
    Event,
    SendMessageAction,
    StatusEvent,
    ResponseChunkEvent,
    ThoughtChunkEvent,
    ErrorEvent,
    UserMessageEvent,
    to_event
)

class Client:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.uri = "ws://127.0.0.1:8000/ws"
        self.websocket: Optional[ClientConnection] = None
        self._listen_task: Optional[asyncio.Task] = None
    
    async def connect(self):
        self.websocket = await websockets.connect(self.uri)

        self._listen_task = asyncio.create_task(self._listen_loop())

    async def _dispatch(self, event: Event):
        match event:
            case ResponseChunkEvent():
                await self.handle_response(event)
            case ThoughtChunkEvent():
                await self.handle_thought(event)
            case StatusEvent():
                await self.handle_status(event)
            case ErrorEvent():
                await self.handle_error(event)
            case UserMessageEvent():
                await self.handle_user_message(event)

    async def _listen_loop(self):
        ws_connection = self.websocket
        if ws_connection:
            try:
                async for message in ws_connection:
                    event_json: dict = json.loads(message)
                    event = to_event(event_json)
                    if event:
                        await self._dispatch(event)
            
            except asyncio.CancelledError:
                pass

            finally:
                await self.handle_disconnect()
    
    async def process_input(self, msg: str):
        if self.websocket:
            action_json = json.dumps(SendMessageAction(text=msg).to_dict())
            await self.websocket.send(action_json)
        else:
            raise ConnectionError("Can't process input, client must be connected to the server")
    
    async def handle_user_message(self, event: UserMessageEvent) -> None: ...
    async def handle_response(self, event: ResponseChunkEvent) -> None: ...
    async def handle_thought(self, event: ThoughtChunkEvent) -> None: ...
    async def handle_status(self, event: StatusEvent) -> None: ...
    async def handle_error(self, event: ErrorEvent) -> None: ...
    async def handle_disconnect(self) -> None: ...

    async def close(self):
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
            self._listen_task = None

        if self.websocket:
            await self.websocket.close()
            self.websocket = None
        
        await self.handle_disconnect()