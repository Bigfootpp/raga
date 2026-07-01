import asyncio
from typing import AsyncIterator
from utils.events import Event, ResponseChunkEvent

# Mock stream class
class Stream:
    async def __aiter__(self) -> AsyncIterator[Event]:
        await asyncio.sleep(1)
        yield ResponseChunkEvent("This")
        await asyncio.sleep(1)
        yield ResponseChunkEvent(" is")
        await asyncio.sleep(1)
        yield ResponseChunkEvent(" a")
        await asyncio.sleep(1)
        yield ResponseChunkEvent(" test")