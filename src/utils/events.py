import json
from dataclasses import dataclass, asdict
from typing import Any, Literal

STATUS_TYPE = Literal["idle", "responding", "thinking"]

EVENT_TYPE = Literal["response", "thought", "status"]
ACTION_TYPE = Literal["send_message", "interrupt"]

MESSAGE_TYPE = Literal[EVENT_TYPE, ACTION_TYPE]

@dataclass
class Message:
    type: MESSAGE_TYPE
    data: dict[str, Any]

    def to_dict(self):
        return asdict(self)
    
    def __str__(self) -> str:
        return json.dumps(self.to_dict())

class Event(Message):
    pass

class Action(Message):
    pass

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

# CLIENT
class SendMessageAction(Action):
    def __init__(self, content: str) -> None:
        super().__init__(type="send_message", data={"text": content})