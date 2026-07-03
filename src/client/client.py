import asyncio
import json
from typing import Optional, Protocol

import websockets
from websockets.asyncio.client import ClientConnection

from utils.events import Event, ResponseChunkEvent, ThoughtChunkEvent, StatusEvent, to_event

class Listener(Protocol):
    async def handle_response(self, chunk: ResponseChunkEvent) -> None: ...
    async def handle_thought(self, chunk: ThoughtChunkEvent) -> None: ...
    async def handle_status(self, chunk: StatusEvent) -> None: ...

class Client:
    def __init__(self, delegate: Listener, uri: str = "ws://127.0.0.1:8000/ws"):
        self.uri = uri
        self.delegate = delegate
        self.websocket: Optional[ClientConnection] = None
        self._listen_task: Optional[asyncio.Task] = None
    
    async def connect(self):
        self.websocket = await websockets.connect(self.uri)

        self._listen_task = asyncio.create_task(self._listen_loop())

    async def _dispatch(self, event: Event):
        match event:
            case ResponseChunkEvent():
                await self.delegate.handle_response(event)
            case ThoughtChunkEvent():
                await self.delegate.handle_thought(event)
            case StatusEvent():
                await self.delegate.handle_status(event)

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

            except Exception:
                pass
    
    async def process_input(self, input: str):
        if self.websocket:
            await self.websocket.send(input)
        else:
            raise ConnectionError("Can't process input, client must be connected to the server")

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