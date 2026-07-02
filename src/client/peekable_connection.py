import json
from typing import Any, AsyncIterable, Iterable, Optional

from websockets.asyncio.client import ClientConnection
from websockets.frames import CloseCode
from websockets.typing import DataLike

from utils.events import EVENT_TYPE

class Connection:
    def __init__(self, websocket: ClientConnection) -> None:
        self.websocket: ClientConnection = websocket
        self.buffer: list[dict[str, Any]] = []
    
    async def _recv(self) -> dict[str, Any]:
        return json.loads(await self.websocket.recv())
    
    async def recv(self) -> dict[str, Any]:
        if self.buffer:
            return self.buffer.pop(0)
        return await self._recv()
    
    async def recv_event(self, *events: EVENT_TYPE) -> dict[str, Any]:
        if not events:
            raise ValueError("At least one event type must be provided.")
            
        for i, msg in enumerate(self.buffer):
            if msg.get("type") in events:
                return self.buffer.pop(i)
        
        while True:
            msg = await self._recv()
            if msg.get("type") in events:
                return msg
            self.buffer.append(msg)

    async def peek(self) -> dict[str, Any]:
        if not self.buffer:
            self.buffer.append(await self._recv())
        return self.buffer[0]
    
    async def send(
        self, 
        message: DataLike | Iterable[DataLike] | AsyncIterable[DataLike], 
        text: Optional[bool] = None
    ) -> None:
        await self.websocket.send(message=message, text=text)
    
    async def close(
        self, 
        code: CloseCode | int = CloseCode.NORMAL_CLOSURE, 
        reason: str = ""
    ) -> None:
        await self.websocket.close(code=code, reason=reason)