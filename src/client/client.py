from typing import Optional, Protocol

import websockets
from websockets.asyncio.client import ClientConnection

from utils.events import ResponseChunkEvent, ThoughtChunkEvent, StatusEvent



class Listener(Protocol):
    async def handle_responses(self, chunk: ResponseChunkEvent) -> None: ...
    async def handle_thought(self, chunk: ThoughtChunkEvent) -> None: ...
    async def handle_status(self, chunk: StatusEvent) -> None: ...

class Client:
    def __init__(self, delegate: Listener, uri: str = "ws://127.0.0.1:8000/ws"):
        self.uri = uri
        self.delegate = delegate
        self.websocket: Optional[ClientConnection] = None
    
    async def connect(self):
        self.websocket = await websockets.connect(self.uri)
    
    async def process_input(self, input: str):
        if self.websocket:
            await self.websocket.send(input)
        else:
            raise ConnectionError("Can't process input, client must be connected to the server")

    async def close(self):
        if self.websocket:
            await self.websocket.close()
            self.websocket = None