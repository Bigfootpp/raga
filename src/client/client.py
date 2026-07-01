import websockets

class Client:
    def __init__(self, uri: str = "ws://127.0.0.1:8000/ws"):
        self.uri = uri
        self.websocket = None
    
    async def connect(self):
        self.websocket = await websockets.connect(self.uri)
    
    async def process_input(self, input: str):
        pass

    async def close(self):
        if self.websocket:
            await self.websocket.close()
            self.websocket = None