from enum import StrEnum
import json
from typing import Any, Literal, Optional, Union, Annotated
from pydantic import BaseModel, Field, TypeAdapter, model_validator, model_serializer

class StatusType(StrEnum):
    IDLE = "idle"
    RESPONDING = "responding"
    THINKING = "thinking"

class ErrorMessage(StrEnum):
    INVALID_FORMAT = "Invalid format"
    SESSION_NOT_FOUND = "Session doesn't exist"
    AGENT_RUNNING = "Agent already running"
    AGENT_NOT_RUNNING = "Agent is not running"
    INTERNAL_ERROR = "An internal error occurred during processing."

class EventType(StrEnum):
    RESPONSE = "chat:streaming:response"
    THOUGHT = "chat:streaming:thought"
    USER_MESSAGE = "chat:message:user"
    ASSISTANT_MESSAGE = "chat:message:assistant"
    THOUGHT_MESSAGE = "chat:message:thought"
    STATUS = "chat:status"
    ERROR = "chat:error"
    INTERRUPTED = "chat:interrupted"

class ActionType(StrEnum):
    SEND_MESSAGE = "chat:send"
    INTERRUPT = "chat:interrupt"

FrameType = EventType | ActionType


class Frame(BaseModel, frozen=True):
    type: FrameType

    @model_validator(mode="before")
    @classmethod
    def flatten_data(cls, data: Any) -> Any:
        if isinstance(data, dict) and "data" in data and isinstance(data["data"], dict):
            nested_data = data.get("data", {})
            return {k: v for k, v in data.items() if k != "data"} | nested_data
        return data

    @model_serializer(mode="wrap")
    def serialize_nested(self, handler) -> dict[str, Any]:
        flat_dict = handler(self)
        msg_type = flat_dict.pop("type")
        return {
            "type": msg_type,
            "data": flat_dict
        }

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()

    def __str__(self) -> str:
        return self.model_dump_json()


class Event(Frame, frozen=True):
    type: EventType


class Action(Frame, frozen=True):
    type: ActionType

# SERVER
class InterruptedEvent(Event, frozen=True):
    type: Literal[EventType.INTERRUPTED] = EventType.INTERRUPTED

class ErrorEvent(Event, frozen=True):
    type: Literal[EventType.ERROR] = EventType.ERROR
    message: ErrorMessage
    details: Optional[Union[list, dict, str]] = None

class StatusEvent(Event, frozen=True):
    type: Literal[EventType.STATUS] = EventType.STATUS
    session_id: str
    state: StatusType

class UserMessageEvent(Event, frozen=True):
    type: Literal[EventType.USER_MESSAGE] = EventType.USER_MESSAGE
    session_id: str
    text: str

class AssistantMessageEvent(Event, frozen=True):
    type: Literal[EventType.ASSISTANT_MESSAGE] = EventType.ASSISTANT_MESSAGE
    session_id: str
    text: str

class ThoughtMessageEvent(Event, frozen=True):
    type: Literal[EventType.THOUGHT_MESSAGE] = EventType.THOUGHT_MESSAGE
    session_id: str
    text: str

class ResponseChunkEvent(Event, frozen=True):
    type: Literal[EventType.RESPONSE] = EventType.RESPONSE
    session_id: str
    chunk: str

class ThoughtChunkEvent(Event, frozen=True):
    type: Literal[EventType.THOUGHT] = EventType.THOUGHT
    session_id: str
    chunk: str

class SendMessageAction(Action, frozen=True):
    type: Literal[ActionType.SEND_MESSAGE] = ActionType.SEND_MESSAGE
    session_id: str
    text: str

class InterruptAction(Action, frozen=True):
    type: Literal[ActionType.INTERRUPT] = ActionType.INTERRUPT
    session_id: str


EventUnion = Annotated[
    Union[
        ErrorEvent,
        StatusEvent,
        ResponseChunkEvent,
        ThoughtChunkEvent,
        UserMessageEvent,
        AssistantMessageEvent,
        ThoughtMessageEvent,
        InterruptedEvent,
    ],
    Field(discriminator="type"),
]

ActionUnion = Annotated[
    Union[
        SendMessageAction,
        InterruptAction,
    ],
    Field(discriminator="type")
]

event_adapter = TypeAdapter(EventUnion)
action_adapter = TypeAdapter(ActionUnion)


def to_event(event_json: Union[str, dict[str, Any]]) -> EventUnion:
    if isinstance(event_json, str):
        event_json = json.loads(event_json)
    return event_adapter.validate_python(event_json)

def to_action(action_json: Union[str, dict[str, Any]]) -> ActionUnion:
    if isinstance(action_json, str):
        action_json = json.loads(action_json)
    return action_adapter.validate_python(action_json)