from typing import AsyncIterable, AsyncIterator, Iterable, Optional, Self

# Imports ajustés selon la structure de la bibliothèque websockets
from websockets.asyncio.client import ClientConnection
from websockets.exceptions import ConnectionClosed
from websockets.frames import CloseCode
from websockets.protocol import State
from websockets.typing import Data, DataLike


class PeekableConnection:
    def __init__(self, websocket: ClientConnection) -> None:
        self.websocket: ClientConnection = websocket
        self.buffer: list[Data] = []
    
    def __aiter__(self) -> Self:
        return self
    
    async def __anext__(self) -> Data:
        if self.websocket.state != State.OPEN and not self.buffer:
            raise StopAsyncIteration
        try:
            return await self.recv()
        except ConnectionClosed:
            raise StopAsyncIteration
    
    async def peeker(self) -> AsyncIterator[Data]:
        next_index = 0
        while self.websocket.state == State.OPEN:
            if next_index < len(self.buffer):
                yield self.buffer[next_index]
                next_index += 1
                continue

            msg = await self.websocket.recv()
            self.buffer.append(msg)
            yield msg

    async def recv(self, decode: Optional[bool] = None) -> Data:
        if self.buffer:
            return self.buffer.pop(0)
        return await self.websocket.recv(decode=decode)

    async def peek(self) -> Data:
        if not self.buffer:
            msg = await self.websocket.recv()
            self.buffer.append(msg)
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