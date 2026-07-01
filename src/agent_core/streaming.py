import asyncio
import json
from dataclasses import dataclass, asdict
from typing import AsyncIterator

@dataclass
class Event:
    type: str
    data: dict

    def to_dict(self):
        return asdict(self)
    
    def __str__(self) -> str:
        return json.dumps(self.to_dict())

class ResponseChunkEvent(Event):
    def __init__(self, content: str):
        super().__init__(type="response", data={"chunk": content})

class ThoughtChunkEvent(Event):
    def __init__(self, content: str):
        super().__init__(type="thought", data={"chunk": content})

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