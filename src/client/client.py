# import websockets

class Client:
    def __init__(self, url: str = "ws://127.0.0.1:8000/ws"):
        self.url = url
        self.connection = None
        self.connected = False
    
    async def connect(self):
        pass