import asyncio
import json
from typing import AsyncGenerator, Literal, Optional, Any, Type, Union, overload
from collections.abc import Callable, Awaitable

from shared.frames_rpc import FrameType, RequestUnion, ResponseUnion, ServerMethodType, SessionListReq, SessionListRes, to_response
import websockets
from websockets.asyncio.client import ClientConnection, connect

from shared.frames import (
    Action,
    AssistantMessageEvent,
    ChatHistoryAction,
    ChatHistoryEvent,
    Event,
    InterruptAction,
    InterruptedEvent,
    SendMessageAction,
    SessionCreateAction,
    SessionCreateEvent,
    StatusEvent,
    ResponseChunkEvent,
    ThoughtChunkEvent,
    ErrorEvent,
    ThoughtMessageEvent,
    UserMessageEvent,
    to_event
)

class BadServerResponseError(Exception):
    pass

class Client:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.uri = "ws://127.0.0.1:8000/ws"
        self.reconnect_delay = 1
        self.connected: bool = False
        self.current_session_id: Optional[str] = None
        
        self.websocket: Optional[ClientConnection] = None
        self.transactions: dict[str, asyncio.Queue[ResponseUnion]] = {}
        self._listen_task: Optional[asyncio.Task] = None
        self._running_connection: bool = False
        self._background_tasks = set()
        self._handlers: dict[Type[Event], Callable[[Any], Awaitable[None]]] = {
            UserMessageEvent: self.handle_user_message,
            AssistantMessageEvent: self.handle_assistant_message,
            ThoughtMessageEvent: self.handle_thought_message,
            ResponseChunkEvent: self.handle_response,
            ThoughtChunkEvent: self.handle_thought,
            StatusEvent: self.handle_status,
            ErrorEvent: self.handle_error,
            InterruptedEvent: self.handle_interrupted,
            SessionCreateEvent: self.handle_session_create,
            ChatHistoryEvent: self.handle_chat_history,
        }

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
            except Exception:
                pass
            finally:
                if self.websocket:
                    self.connected = False
                    websocket = self.websocket
                    self.websocket = None
                    try:
                        if websocket.state == websockets.State.OPEN:
                            await websocket.close()
                    except Exception:
                        pass
                await self.handle_disconnect()

            if self._running_connection:
                await asyncio.sleep(self.reconnect_delay)

    async def _listen_loop(self):
        if not self.websocket:
            return
            
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
                    event = to_event(frame_json)
                    if event:
                        await self._dispatch(event)
            except Exception:
                pass

    async def _dispatch(self, event: Event):
        handler = self._handlers.get(type(event))
        if handler:
            await handler(event)
    
    async def send(self, action: Action):
        if self.websocket and self.websocket.state == websockets.State.OPEN:
            action_json = json.dumps(action.to_dict())
            await self.websocket.send(action_json)
        else:
            raise ConnectionError("Unable to send the message, the client is not connected.")

    async def process_input(self, msg: str):
        if not self.current_session_id:
            await self.create_session()
            await asyncio.sleep(0.1)
        else:
            await self.send(SendMessageAction(text=msg, session_id=self.current_session_id))
    
    async def interrupt(self):
        if not self.current_session_id:
            return
        await self.send(InterruptAction(session_id=self.current_session_id))
    
    
    @overload
    async def send_request(self, request: RequestUnion[Literal[False]]) -> ResponseUnion: ...
    @overload
    async def send_request(self, request: RequestUnion[Literal[True]]) -> AsyncGenerator[ResponseUnion, None]: ...
    
    async def send_request(self, request: RequestUnion[Any]) -> Union[AsyncGenerator[ResponseUnion, None], ResponseUnion]:
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
                        yield response
                        if not response.has_more:
                            break
                finally:
                    self.transactions.pop(req_id, None)
            
            return generator()
        else:
            try:
                return await queue.get()
            finally:
                self.transactions.pop(req_id, None)


    async def handle_connect(self) -> None: ...
    async def handle_disconnect(self) -> None: ...
    async def handle_user_message(self, event: UserMessageEvent) -> None: ...
    async def handle_assistant_message(self, event: AssistantMessageEvent) -> None: ...
    async def handle_thought_message(self, event: ThoughtMessageEvent) -> None: ...
    async def handle_response(self, event: ResponseChunkEvent) -> None: ...
    async def handle_thought(self, event: ThoughtChunkEvent) -> None: ...
    async def handle_status(self, event: StatusEvent) -> None: ...
    async def handle_error(self, event: ErrorEvent) -> None: ...
    async def handle_interrupted(self, event: InterruptedEvent) -> None: ...
    async def handle_session_create(self, event: SessionCreateEvent) -> None: ...
    async def handle_chat_history(self, event: ChatHistoryEvent) -> None: ...

    async def list_sessions(self) -> list[str]:
        response: SessionListRes = await self.send_request(SessionListReq())
        if response.method != ServerMethodType.SESSION_LIST:
            raise BadServerResponseError(
                f"Wrong response method received; got {response.method}, excepted {ServerMethodType.SESSION_LIST}"
            )
        return response.sessions

    async def create_session(self) -> None:
        await self.send(SessionCreateAction())

    async def load_chat_history(self, session_id: str) -> None:
        await self.send(ChatHistoryAction(session_id=session_id))

    def set_session(self, session_id: str) -> None:
        self.current_session_id = session_id

    async def close(self):
        self._running_connection = False

        if self.websocket:
            try:
                if self.websocket.state == websockets.State.OPEN:
                    await self.websocket.close()
            except Exception:
                pass
            self.websocket = None

        if self._listen_task:
            if not self._listen_task.done():
                self._listen_task.cancel()
                try:
                    await self._listen_task
                except asyncio.CancelledError:
                    pass
            self._listen_task = None