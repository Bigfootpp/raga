import json
from dataclasses import dataclass, asdict
from typing import Literal

STATUS_TYPE = Literal["idle", "responding", "thinking"]
EVENT_TYPE = Literal["response", "thought", "status"]

@dataclass
class Event:
    type: str
    data: dict

    def to_dict(self):
        return asdict(self)
    
    def __str__(self) -> str:
        return json.dumps(self.to_dict())

# SERVER
class StatusEvent(Event):
    def __init__(self, content: STATUS_TYPE):
        super().__init__(type="status", data={"state": content})

class ResponseChunkEvent(Event):
    def __init__(self, content: str):
        super().__init__(type="response", data={"chunk": content})

class ThoughtChunkEvent(Event):
    def __init__(self, content: str):
        super().__init__(type="thought", data={"chunk": content})
