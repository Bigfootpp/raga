import json
from dataclasses import dataclass, asdict
from typing import Literal

@dataclass
class Event:
    type: str
    data: dict

    def to_dict(self):
        return asdict(self)
    
    def __str__(self) -> str:
        return json.dumps(self.to_dict())

class StatusEvent(Event):
    def __init__(self, content: Literal["idle", "responding", "thinking"]):
        super().__init__(type="status", data={"state": content})

class ResponseChunkEvent(Event):
    def __init__(self, content: str):
        super().__init__(type="response", data={"chunk": content})

class ThoughtChunkEvent(Event):
    def __init__(self, content: str):
        super().__init__(type="thought", data={"chunk": content})