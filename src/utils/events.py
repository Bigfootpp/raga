import json
from dataclasses import dataclass, asdict
from typing import Any, Literal, Optional

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

def to_event(event_json: dict[str, Any]) -> Optional[Event]:
    event_type: Optional[str] = event_json.get("type")
    event_data: Optional[dict[str, Any]] = event_json.get("data")
    
    if event_type and event_data:
        match event_type:
            case "response":
                return ResponseChunkEvent(event_data.get("chunk", ""))
            case "thought":
                return ThoughtChunkEvent(event_data.get("chunk", ""))
            case "status":
                return StatusEvent(event_data.get("state", ""))
    
    return