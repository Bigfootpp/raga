from enum import StrEnum
import json
from typing import Any, Literal, Optional, Union, Annotated
from pydantic import BaseModel, Field, TypeAdapter

class RoleType(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ToolCallFunction(BaseModel, frozen=True):
    name: str
    arguments: str


class ToolCall(BaseModel, frozen=True):
    id: str
    type: str = "function"
    function: ToolCallFunction


class Message(BaseModel, frozen=True):
    role: RoleType

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)

    def __str__(self) -> str:
        return self.model_dump_json(exclude_none=True)


class SystemMessage(Message, frozen=True):
    role: Literal[RoleType.SYSTEM] = RoleType.SYSTEM
    content: str


class UserMessage(Message, frozen=True):
    role: Literal[RoleType.USER] = RoleType.USER
    content: str


class AssistantMessage(Message, frozen=True):
    role: Literal[RoleType.ASSISTANT] = RoleType.ASSISTANT
    content: Optional[str] = None
    reasoning: Optional[str] = None
    reasoning_content: Optional[str] = None
    tool_calls: Optional[list[ToolCall]] = None


class ToolMessage(Message, frozen=True):
    role: Literal[RoleType.TOOL] = RoleType.TOOL
    tool_call_id: str
    name: str
    content: str


MessageUnion = Annotated[
    Union[SystemMessage, UserMessage, AssistantMessage, ToolMessage],
    Field(discriminator="role")
]

message_adapter = TypeAdapter(MessageUnion)


def to_message(message_json: Union[str, dict[str, Any]]) -> MessageUnion:
    if isinstance(message_json, str):
        message_json = json.loads(message_json)
    return message_adapter.validate_python(message_json)