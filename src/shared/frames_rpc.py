from enum import StrEnum
import json
from typing import Any, Literal, Optional, Union, Annotated, cast
from uuid import uuid4
from pydantic import BaseModel, Field, TypeAdapter, model_validator, model_serializer
from shared.messages import MessageUnion

class ErrorMessageRPC(StrEnum):
    INVALID_FORMAT = "Invalid format"
    SESSION_NOT_FOUND = "Session doesn't exist"
    AGENT_RUNNING = "Agent already running"
    AGENT_NOT_RUNNING = "Agent is not running"
    INTERNAL_ERROR = "An internal error occurred during processing."

class FrameType(StrEnum):
    REQUEST = "request"
    RESPONSE = "response"
    EVENT = "event"

class StatusType(StrEnum):
    IDLE = "idle"
    RESPONDING = "responding"
    THINKING = "thinking"

# Client -> Server -> Client
class ServerMethodType(StrEnum):
    SESSION_LIST = "sessions:list"
    SESSION_CREATE = "sessions:create"
    SEND_MESSAGE = "chat:send"
    # INTERRUPT = "chat:interrupt"
    CHAT_HISTORY = "chat:history"
    ERROR = "error"

# Client -> Server
class ServerEventType(StrEnum):
    pass

# Server -> Client -> Server
class ClientMethodType(StrEnum):
    pass

# Server -> Client
class ClientEventType(StrEnum):
    pass

MethodType = ServerMethodType | ClientMethodType
EventType = ServerEventType | ClientEventType

type bool_type = Literal[True] | Literal[False]

class Request[StreamType: bool_type](BaseModel, frozen=True):
    type: Literal[FrameType.REQUEST] = FrameType.REQUEST
    id: str = Field(default_factory=lambda: str(uuid4()))
    method: MethodType
    stream: StreamType = cast(StreamType, False)

    @model_validator(mode="before")
    @classmethod
    def flatten_param(cls, param: Any) -> Any:
        if isinstance(param, dict) and "param" in param and isinstance(param["param"], dict):
            nested_data = param.get("param", {})
            return {k: v for k, v in param.items() if k != "param"} | nested_data
        return param

    @model_serializer(mode="wrap")
    def serialize_nested(self, handler) -> dict[str, Any]:
        flat_dict: dict = handler(self)
        msg_type = flat_dict.pop("type")
        req_id = flat_dict.pop("id")
        method = flat_dict.pop("method")
        stream = flat_dict.pop("stream")
        return {
            "type": msg_type,
            "id": req_id,
            "method": method,
            "stream": stream,
            "param": flat_dict
        }

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()

    def __str__(self) -> str:
        return self.model_dump_json()

class Response(BaseModel, frozen=True):
    type: Literal[FrameType.RESPONSE] = FrameType.RESPONSE
    id: str
    ok: Literal[True] = True
    method: MethodType
    has_more: bool = False

    @model_validator(mode="before")
    @classmethod
    def flatten_payload(cls, payload: Any) -> Any:
        if isinstance(payload, dict) and "payload" in payload and isinstance(payload["payload"], dict):
            nested_data = payload.get("payload", {})
            return {k: v for k, v in payload.items() if k != "payload"} | nested_data
        return payload

    @model_serializer(mode="wrap")
    def serialize_nested(self, handler) -> dict[str, Any]:
        flat_dict: dict = handler(self)
        msg_type = flat_dict.pop("type")
        req_id = flat_dict.pop("id")
        method = flat_dict.pop("method")
        ok = flat_dict.pop("ok")
        has_more = flat_dict.pop("has_more")
        return {
            "type": msg_type,
            "id": req_id,
            "ok": ok,
            "method": method,
            "has_more": has_more,
            "payload": flat_dict,
        }

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()

    def __str__(self) -> str:
        return self.model_dump_json()

class Event(BaseModel, frozen=True):
    type: Literal[FrameType.EVENT] = FrameType.EVENT
    event: EventType

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
        event = flat_dict.pop("event")
        return {
            "type": msg_type,
            "event": event,
            "data": flat_dict
        }

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()

    def __str__(self) -> str:
        return self.model_dump_json()

# Server
class ErrorRes(Response, frozen=True):
    method: Literal[ServerMethodType.ERROR] = ServerMethodType.ERROR
    message: ErrorMessageRPC
    details: Optional[Union[list, dict, str]] = None

class SessionListReq[StreamType: bool_type](Request[StreamType], frozen=True):
    method: Literal[ServerMethodType.SESSION_LIST] = ServerMethodType.SESSION_LIST

class SessionListRes(Response, frozen=True):
    method: Literal[ServerMethodType.SESSION_LIST] = ServerMethodType.SESSION_LIST
    sessions: list[str]

class SessionCreateReq[StreamType: bool_type](Request[StreamType], frozen=True):
    method: Literal[ServerMethodType.SESSION_CREATE] = ServerMethodType.SESSION_CREATE

class SessionCreateRes(Response, frozen=True):
    method: Literal[ServerMethodType.SESSION_CREATE] = ServerMethodType.SESSION_CREATE
    session_id: str

class ChatHistoryReq[StreamType: bool_type](Request[StreamType], frozen=True):
    method: Literal[ServerMethodType.CHAT_HISTORY] = ServerMethodType.CHAT_HISTORY
    session_id: str

class ChatHistoryRes(Response, frozen=True):
    method: Literal[ServerMethodType.CHAT_HISTORY] = ServerMethodType.CHAT_HISTORY
    messages: list[MessageUnion]

class SendMessageReq[StreamType: bool_type](Request[StreamType], frozen=True):
    method: Literal[ServerMethodType.SEND_MESSAGE] = ServerMethodType.SEND_MESSAGE
    text: str
    session_id: str

class SendMessageRes(Response, frozen=True):
    method: Literal[ServerMethodType.SEND_MESSAGE] = ServerMethodType.SEND_MESSAGE
    thought_chunk: Optional[str]
    chunk: Optional[str]

# Client
type ResponseType[ResType: Response] = Union[ResType, ErrorRes]

type RequestUnion[StreamType: bool_type] = Annotated[
    Union[
        SessionListReq[StreamType],
        SessionCreateReq[StreamType],
        ChatHistoryReq[StreamType],
        SendMessageReq[StreamType],
    ],
    Field(discriminator="method")
]

ResponseUnion = Annotated[
    Union[
        SessionListRes,
        SessionCreateRes,
        ChatHistoryRes,
        SendMessageRes,
        ErrorRes,
    ],
    Field(discriminator="method")
]

request_adapter = TypeAdapter(RequestUnion[bool_type])
response_adapter = TypeAdapter(ResponseUnion)

def to_request(req_json: Union[str, dict[str, Any]]) -> RequestUnion[bool_type]:
    if isinstance(req_json, str):
        req_json = json.loads(req_json)
    return request_adapter.validate_python(req_json)

def to_response(res_json: Union[str, dict[str, Any]]) -> ResponseUnion:
    if isinstance(res_json, str):
        res_json = json.loads(res_json)
    return response_adapter.validate_python(res_json)