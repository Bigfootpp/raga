import asyncio
from typing import AsyncIterator
from utils.messages import Event, ResponseChunkEvent

# Mock stream class
class Stream:
    async def __aiter__(self) -> AsyncIterator[Event]:
        await asyncio.sleep(1)
        yield ResponseChunkEvent(chunk="This")
        await asyncio.sleep(1)
        yield ResponseChunkEvent(chunk=" is")
        await asyncio.sleep(1)
        yield ResponseChunkEvent(chunk=" a")
        await asyncio.sleep(1)
        yield ResponseChunkEvent(chunk=" test")