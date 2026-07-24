import asyncio
from typing import AsyncGenerator, AsyncIterator, Awaitable, Optional

from agent_core.harness import AgentAlreadyRunning, AgentNotRunning, ExecutionInterrupted, Harness
from agent_core.session_manager import SessionManager, SessionNotFound
from fastapi import WebSocket
from gateway.connection_manager import ConnectionManager
from shared.frames_rpc import (
    ChatHistoryReq,
    ChatHistoryRes,
    ErrorMessageRPC,
    ErrorRes,
    ResponseType,
    SendMessageReq,
    SendMessageRes,
    SessionListReq,
    SessionListRes,
    SessionCreateReq,
    SessionCreateRes,
)
from shared.config import config
from shared.frames import (
    Action,
    ErrorEvent,
    ErrorMessage,
    Event,
    InterruptAction,
    InterruptedEvent,
    StatusEvent,
    StatusType,
)
from shared.messages import AssistantMessage, MessageUnion

def idle_status(session_id: str) -> StatusEvent: return StatusEvent(state=StatusType.IDLE, session_id=session_id)
def responding_status(session_id: str) -> StatusEvent: return StatusEvent(state=StatusType.RESPONDING, session_id=session_id)
def thinking_status(session_id: str) -> StatusEvent: return StatusEvent(state=StatusType.THINKING, session_id=session_id)

def build_send_message_response(request_id: str, has_more: bool, message: AssistantMessage) -> SendMessageRes:
    content = message.content
    thought = message.reasoning_content
    return SendMessageRes(id=request_id, has_more=has_more, content=content, reasoning_content=thought)

# TODO: Migrate chat:interrupt to RPC
class Server:
    def __init__(self, session_manager: SessionManager) -> None:
        connection_manager = ConnectionManager()
        connection_manager.on(SessionListReq, self._session_list)
        connection_manager.on(SessionCreateReq, self._session_create)
        connection_manager.on(ChatHistoryReq, self._chat_history)
        connection_manager.on(SendMessageReq, self._send_message)

        self.harness = Harness(session_manager)
        self.session_manager = session_manager
        self.connection_manager = connection_manager
        self.task: asyncio.Task = asyncio.create_task(self._listen_loop())

    @classmethod
    async def create(cls) -> "Server":
        session_manager = await SessionManager.create(config.DB_PATH)
        return cls(session_manager)

    async def _session_list(self, request: SessionListReq) -> AsyncGenerator[ResponseType[SessionListRes], None]:
        sessions = await self.session_manager.get_session_ids()
        yield SessionListRes(sessions=sessions, id=request.id)

    async def _session_create(self, request: SessionCreateReq) -> AsyncGenerator[ResponseType[SessionCreateRes], None]:
        session = await self.session_manager.new_session()
        if session.session_id:
            yield SessionCreateRes(id=request.id, session_id=session.session_id)
        else:
            yield ErrorRes(id=request.id, message=ErrorMessageRPC.INTERNAL_ERROR)

    async def _chat_history(self, request: ChatHistoryReq) -> AsyncGenerator[ResponseType[ChatHistoryRes], None]:
        try:
            session = await self.session_manager.load_session(request.session_id)
            yield ChatHistoryRes(id=request.id, messages=session.history)
        except SessionNotFound:
            yield ErrorRes(id=request.id, message=ErrorMessageRPC.SESSION_NOT_FOUND)

    async def _send_message(self, request: SendMessageReq) -> AsyncGenerator[ResponseType[SendMessageRes], None]:
        if not request.stream:
            yield ErrorRes(id=request.id, message=ErrorMessageRPC.STREAM_REQUIRED)

        try:
            last_chunk: Optional[MessageUnion] = None
            async for chunk in self.harness.process_input(request.text, request.session_id):
                if not isinstance(chunk, AssistantMessage):
                    continue

                if last_chunk:
                    yield build_send_message_response(request_id=request.id, has_more=True, message=last_chunk)

                last_chunk = chunk

            if last_chunk:
                yield build_send_message_response(request_id=request.id, has_more=False, message=last_chunk)

        except AgentAlreadyRunning:
            yield ErrorRes(id=request.id, message=ErrorMessageRPC.AGENT_RUNNING)

        except SessionNotFound:
            yield ErrorRes(id=request.id, message=ErrorMessageRPC.SESSION_NOT_FOUND)

        except ExecutionInterrupted:
            return

    async def connect(self, ws: WebSocket) -> Awaitable[None]:
        return await self.connection_manager.connect(ws=ws)

    async def _listen_loop(self):
        while True:
            ws, action = await self.connection_manager.recv_action()
            try:
                async for event in self._dispatch(action=action):
                    await ws.send_json(event.to_dict())
            except Exception as e:
                need_break = self.connection_manager.handle_error(e=e, ws=ws)
                if need_break:
                    break
        try:
            await ws.close()
        except Exception:
            pass

    async def _interrupt(self, action: InterruptAction):
        try:
            await self.harness.interrupt(action.session_id)
            yield InterruptedEvent()
            yield idle_status(action.session_id)
        except AgentNotRunning:
            yield ErrorEvent(message=ErrorMessage.AGENT_NOT_RUNNING)
        except SessionNotFound:
            yield ErrorEvent(message=ErrorMessage.SESSION_NOT_FOUND)

    async def _dispatch(self, action: Action) -> AsyncIterator[Event]:
        match action:
            case InterruptAction():
                async for event in self._interrupt(action):
                    yield event