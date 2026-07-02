from typing import Optional
from client.peekable_connection import PeekableConnection

import websockets

class StreamResponse:
    pass

class Client:
    def __init__(self, uri: str = "ws://127.0.0.1:8000/ws"):
        self.uri = uri
        self.websocket: Optional[PeekableConnection] = None
    
    async def connect(self):
        self.websocket = PeekableConnection(await websockets.connect(self.uri))
    
    async def process_input(self, input: str):
        if self.websocket:
            await self.websocket.send("")
        else:
            raise ConnectionError("Can't process input, client must be connected to the server")

    async def close(self):
        if self.websocket:
            await self.websocket.close()
            self.websocket = None