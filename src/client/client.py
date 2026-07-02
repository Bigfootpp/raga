from typing import Optional
# from client.peekable_connection import PeekableConnection

import websockets
from websockets.asyncio.client import ClientConnection

class StreamResponse:
    def __init__(self, websocket: ClientConnection):
        self.websocket = websocket
    
    def __aiter__(self):
        return self
    
    def __anext__(self):
        pass
        

class Client:
    def __init__(self, uri: str = "ws://127.0.0.1:8000/ws"):
        self.uri = uri
        self.websocket: Optional[ClientConnection] = None
    
    async def connect(self):
        self.websocket = await websockets.connect(self.uri)
    
    async def process_input(self, input: str):
        if self.websocket:
            await self.websocket.send("")
        else:
            raise ConnectionError("Can't process input, client must be connected to the server")

    async def close(self):
        if self.websocket:
            await self.websocket.close()
            self.websocket = None