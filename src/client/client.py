import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any, Literal, overload

import websockets
from pydantic import ValidationError
from websockets.asyncio.client import ClientConnection, connect

from shared.frames_rpc import (
    ChatHistoryReq,
    ChatHistoryRes,
    ErrorMessageRPC,
    ErrorRes,
    FrameType,
    InterruptReq,
    InterruptRes,
    RequestUnion,
    ResponseUnion,
    SendMessageReq,
    SendMessageRes,
    SessionCreateReq,
    SessionCreateRes,
    SessionListReq,
    SessionListRes,
    to_response,
)
from shared.messages import AssistantMessage, MessageUnion


class BadServerResponseError(Exception):
    pass

class SessionNotFound(Exception):
    pass

class ServerInternalError(Exception):
    pass

class AgentRunningError(Exception):
    pass

class AgentNotRunningError(Exception):
    pass

class StreamRequiredError(Exception):
    pass

VALIDATION_MAP: dict[ErrorMessageRPC, type[Exception]] = {
    ErrorMessageRPC.SESSION_NOT_FOUND: SessionNotFound,
    ErrorMessageRPC.INTERNAL_ERROR: ServerInternalError,
    ErrorMessageRPC.AGENT_RUNNING: AgentRunningError,
    ErrorMessageRPC.AGENT_NOT_RUNNING: AgentNotRunningError,
    ErrorMessageRPC.STREAM_REQUIRED: StreamRequiredError,
}

def validate_response(response: ResponseUnion):
    if isinstance(response, ErrorRes):
        error = VALIDATION_MAP.get(response.message, None)
        if error:
            raise error(response.message)

def validate_expected_response[T: ResponseUnion](
    response: ResponseUnion,
    *args: type[T]
) -> T:
    if not isinstance(response, args):
        raise BadServerResponseError(
            f"Wrong response method received; got {getattr(response, 'method', None)}, expected {args}"
        )
    return response

class Client:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.uri = "ws://127.0.0.1:8000/ws"
        self.reconnect_delay = 1
        self.connected: bool = False

        self.websocket: ClientConnection | None = None
        self.transactions: dict[str, asyncio.Queue[ResponseUnion]] = {}
        self._listen_task: asyncio.Task | None = None
        self._running_connection: bool = False
        self._background_tasks = set()

    async def connect(self):
        if self._running_connection:
            return

        self._running_connection = True
        self._listen_task = asyncio.create_task(self._reconnect_loop())

    async def _reconnect_loop(self):
        while self._running_connection:
            try:
                self.websocket = await connect(self.uri)
                self.connected = True
                await self.handle_connect()

                await self._listen_loop()

            except asyncio.CancelledError:
                break
            finally:
                if self.websocket:
                    self.connected = False
                    websocket = self.websocket
                    self.websocket = None
                    if websocket.state == websockets.State.OPEN:
                        await websocket.close()
                await self.handle_disconnect()

            if self._running_connection:
                await asyncio.sleep(self.reconnect_delay)

    async def _listen_loop(self):
        if not self.websocket:
            return

        try:
            async for message in self.websocket:
                try:
                    frame_json: dict = json.loads(message)
                    if frame_json.get("type", "") == FrameType.RESPONSE:
                        response = to_response(frame_json)
                        res_id = response.id
                        queue = self.transactions.get(res_id)
                        if queue:
                            await queue.put(response)
                    else:
                        pass
                except (json.JSONDecodeError, ValidationError):
                    pass
        except websockets.ConnectionClosedError:
            pass

    @overload
    async def send_request(self, request: RequestUnion[Literal[False]]) -> ResponseUnion: ...
    @overload
    async def send_request(self, request: RequestUnion[Literal[True]]) -> AsyncGenerator[ResponseUnion, None]: ...
    async def send_request(self, request: RequestUnion[Any]) -> AsyncGenerator[ResponseUnion, None] | ResponseUnion:
        if not self.websocket or not self.websocket.state == websockets.State.OPEN:
            raise ConnectionError("Unable to send the message, the client is not connected.")

        req_id = request.id
        queue: asyncio.Queue[ResponseUnion] = asyncio.Queue()
        self.transactions[req_id] = queue

        try:
            req_json = json.dumps(request.to_dict())
            await self.websocket.send(req_json)
        except Exception:
            self.transactions.pop(req_id, None)
            raise

        if request.stream:
            async def generator() -> AsyncGenerator[ResponseUnion, None]:
                try:
                    while True:
                        response = await queue.get()
                        validate_response(response)
                        yield response
                        if not response.has_more:
                            break
                finally:
                    self.transactions.pop(req_id, None)

            return generator()
        else:
            try:
                response = await queue.get()
                validate_response(response)
                return response
            finally:
                self.transactions.pop(req_id, None)


    async def handle_connect(self) -> None: ...
    async def handle_disconnect(self) -> None: ...

    async def list_sessions(self) -> list[str]:
        response = await self.send_request(SessionListReq())
        response = validate_expected_response(response, SessionListRes)
        return response.sessions

    async def create_session(self) -> str:
        response = await self.send_request(SessionCreateReq())
        response = validate_expected_response(response, SessionCreateRes)
        return response.session_id

    async def load_chat_history(self, session_id: str) -> list[MessageUnion]:
        response = await self.send_request(ChatHistoryReq(session_id=session_id))
        response = validate_expected_response(response, ChatHistoryRes)
        return response.messages

    async def process_input(self, session_id: str, msg: str) -> AsyncGenerator[MessageUnion, None]:
        async for chunk in await self.send_request(SendMessageReq(session_id=session_id, stream=True, text=msg)):
            chunk = validate_expected_response(chunk, SendMessageRes)
            yield AssistantMessage(
                content=chunk.content,
                reasoning_content=chunk.reasoning_content
            )

    async def interrupt(self, session_id: str):
        response = await self.send_request(InterruptReq(session_id=session_id))
        validate_expected_response(response, InterruptRes)

    async def close(self):
        self._running_connection = False

        if self.websocket:
            if self.websocket.state == websockets.State.OPEN:
                await self.websocket.close()
            self.websocket = None

        if self._listen_task:
            if not self._listen_task.done():
                self._listen_task.cancel()
                try:
                    await self._listen_task
                except asyncio.CancelledError:
                    pass
            self._listen_task = None