from collections.abc import AsyncGenerator, Awaitable

from fastapi import WebSocket

from agent_core.harness import (
    AgentAlreadyRunning,
    AgentNotRunning,
    ExecutionInterrupted,
    Harness,
)
from agent_core.session_manager import SessionManager, SessionNotFound
from gateway.connection_manager import ConnectionManager
from shared.config import config
from shared.frames import (
    ChatHistoryReq,
    ChatHistoryRes,
    ErrorMessage,
    ErrorRes,
    InterruptReq,
    InterruptRes,
    ResponseType,
    SendMessageReq,
    SendMessageRes,
    SessionCreateReq,
    SessionCreateRes,
    SessionListReq,
    SessionListRes,
)
from shared.messages import AssistantMessage, MessageUnion


def build_send_message_response(request_id: str, has_more: bool, message: AssistantMessage) -> SendMessageRes:
    content = message.content
    thought = message.reasoning_content
    return SendMessageRes(id=request_id, has_more=has_more, content=content, reasoning_content=thought)

class Server:
    def __init__(self, session_manager: SessionManager) -> None:
        connection_manager = ConnectionManager()
        connection_manager.on(SessionListReq, self._session_list)
        connection_manager.on(SessionCreateReq, self._session_create)
        connection_manager.on(ChatHistoryReq, self._chat_history)
        connection_manager.on(SendMessageReq, self._send_message)
        connection_manager.on(InterruptReq, self._interrupt_request)

        self.harness = Harness(session_manager)
        self.session_manager = session_manager
        self.connection_manager = connection_manager

    @classmethod
    async def create(cls) -> "Server":
        session_manager = await SessionManager.create(config.DB_PATH)
        return cls(session_manager)

    async def _interrupt_request(self, request: InterruptReq) -> AsyncGenerator[
        ResponseType[InterruptRes],
        None
    ]:
        try:
            await self.harness.interrupt(request.session_id)
            yield InterruptRes(id=request.id)
        except AgentNotRunning:
            yield ErrorRes(id=request.id, message=ErrorMessage.AGENT_NOT_RUNNING)
        except SessionNotFound:
            yield ErrorRes(id=request.id, message=ErrorMessage.SESSION_NOT_FOUND)

    async def _session_list(self, request: SessionListReq) -> AsyncGenerator[
        ResponseType[SessionListRes],
        None
    ]:
        sessions = await self.session_manager.get_session_ids()
        yield SessionListRes(sessions=sessions, id=request.id)

    async def _session_create(self, request: SessionCreateReq) -> AsyncGenerator[
        ResponseType[SessionCreateRes],
        None
    ]:
        session = await self.session_manager.new_session()
        if session.session_id:
            yield SessionCreateRes(id=request.id, session_id=session.session_id)
        else:
            yield ErrorRes(id=request.id, message=ErrorMessage.INTERNAL_ERROR)

    async def _chat_history(self, request: ChatHistoryReq) -> AsyncGenerator[
        ResponseType[ChatHistoryRes],
        None
    ]:
        try:
            session = await self.session_manager.load_session(request.session_id)
            yield ChatHistoryRes(id=request.id, messages=session.history)
        except SessionNotFound:
            yield ErrorRes(id=request.id, message=ErrorMessage.SESSION_NOT_FOUND)

    async def _send_message(self, request: SendMessageReq) -> AsyncGenerator[
        ResponseType[SendMessageRes],
        None
    ]:
        if not request.stream:
            yield ErrorRes(id=request.id, message=ErrorMessage.STREAM_REQUIRED)

        try:
            last_chunk: MessageUnion | None = None
            async for chunk in self.harness.process_input(request.text, request.session_id):
                if not isinstance(chunk, AssistantMessage):
                    continue

                if last_chunk:
                    yield build_send_message_response(request_id=request.id, has_more=True, message=last_chunk)

                last_chunk = chunk

            if last_chunk:
                yield build_send_message_response(request_id=request.id, has_more=False, message=last_chunk)

        except AgentAlreadyRunning:
            yield ErrorRes(id=request.id, message=ErrorMessage.AGENT_RUNNING)

        except SessionNotFound:
            yield ErrorRes(id=request.id, message=ErrorMessage.SESSION_NOT_FOUND)

        except ExecutionInterrupted:
            return

    async def connect(self, ws: WebSocket) -> Awaitable[None]:
        return await self.connection_manager.connect(ws=ws)