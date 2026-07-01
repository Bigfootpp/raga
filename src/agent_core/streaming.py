from typing import AsyncIterator

class Event:
    def __init__(self, type: str, data: dict):
        self.type = type
        self.data = data
    
    def to_dict(self):
        return {
            "type": self.type,
            "data": self.data
        }
    
    def __str__(self) -> str:
        return str(self.to_dict())

class ResponseChunkEvent(Event):
    def __init__(self, content: str):
        super().__init__("response", {
            "chunk": content
        })

class ThoughtChunkEvent(Event):
    def __init__(self, content: str):
        super().__init__("thought", {
            "chunk": content
        })

class Stream:
    def __init__(self):
        pass

    async def __aiter__(self) -> AsyncIterator[Event]:
        yield ResponseChunkEvent("This")
        yield ResponseChunkEvent(" is")
        yield ResponseChunkEvent(" a")
        yield ResponseChunkEvent(" test")