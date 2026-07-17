import asyncio
import traceback
from typing import AsyncIterator, Awaitable

from agent_core.harness import AgentAlreadyRunning, AgentNotRunning, ExecutionInterrupted, Harness
from agent_core.session_manager import SessionManager, SessionNotFound
from fastapi import WebSocket, WebSocketDisconnect, WebSocketException
from pydantic import ValidationError
from utils import async_utils
from utils.async_utils import aenumerate
from shared.config import config
from shared.frames import (
    Action,
    AssistantMessageEvent,
    ChatHistoryAction,
    ChatHistoryEvent,
    ErrorEvent,
    ErrorMessage,
    Event,
    InterruptAction,
    InterruptedEvent,
    SendMessageAction,
    SessionCreateAction,
    SessionCreateEvent,
    SessionListAction,
    SessionListEvent,
    StatusEvent,
    ResponseChunkEvent,
    ThoughtChunkEvent,
    StatusType,
    ThoughtMessageEvent,
    UserMessageEvent,
    to_action,
)
from shared.messages import AssistantMessage

def idle_status(session_id: str) -> StatusEvent: return StatusEvent(state=StatusType.IDLE, session_id=session_id)
def responding_status(session_id: str) -> StatusEvent: return StatusEvent(state=StatusType.RESPONDING, session_id=session_id)
def thinking_status(session_id: str) -> StatusEvent: return StatusEvent(state=StatusType.THINKING, session_id=session_id)

class Server:
    def __init__(self, session_manager: SessionManager) -> None:
        self.harness = Harness(session_manager)
        self.session_manager = session_manager
        self.connections: set[WebSocket] = set()
        self.events: dict[WebSocket, asyncio.Event] = {}
        self.tasks: dict[WebSocket, asyncio.Task] = {}
    
    @classmethod
    async def create(cls) -> "Server":
        session_manager = await SessionManager.create(config.DB_PATH)
        return cls(session_manager)

    async def connect(self, ws: WebSocket) -> Awaitable[None]:
        self.connections.add(ws)
        task = asyncio.create_task(self._listen_loop(ws=ws))
        self.tasks[ws] = task
        self.events[ws] = asyncio.Event()
        return self.disconnected(ws=ws)
    
    async def disconnected(self, ws: WebSocket):
        event = self.events.get(ws)
        if event is None:
            return
        
        await event.wait()
        self.events.pop(ws)
    
    async def _handle_error(self, e: Exception, ws: WebSocket) -> bool:
        print(f"Error: ({e.__class__.__name__})")
        print(traceback.print_exc())
        match e:
            case ValidationError():
                try:
                    await ws.send_json(ErrorEvent(message=ErrorMessage.INVALID_FORMAT, details=e.errors()).to_dict())
                except Exception:
                    return True
                return False
            case WebSocketException() | WebSocketDisconnect():
                return True
            case asyncio.CancelledError():
                return True
            case Exception():
                try:
                    await ws.send_json(ErrorEvent(message=ErrorMessage.INTERNAL_ERROR).to_dict())
                except Exception:
                    return True
                return False
    
    @async_utils.background_task
    async def _handle(self, ws: WebSocket, action_json: str):
        try:
            action: Action = to_action(action_json)

            async for event in self._dispatch(action=action):
                await ws.send_json(event.to_dict())
        except Exception as e:
            await self._handle_error(e=e, ws=ws)
            return

    async def _listen_loop(self, ws: WebSocket):
        while True:
            try:
                action: str = await ws.receive_text()
                self._handle(ws=ws, action_json=action)
            except Exception as e:
                need_break = self._handle_error(e=e, ws=ws)
                if need_break:
                    break
        self.tasks.pop(ws)
        self.connections.remove(ws)
        try:
            await ws.close()
        except Exception:
            pass
        event = self.events.get(ws)
        if event is not None:
            event.set()
    
    async def _interrupt(self, action: InterruptAction):
        try:
            await self.harness.interrupt(action.session_id)
            yield InterruptedEvent()
            yield idle_status(action.session_id)
        except AgentNotRunning:
            yield ErrorEvent(message=ErrorMessage.AGENT_NOT_RUNNING)
        except SessionNotFound:
            yield ErrorEvent(message=ErrorMessage.SESSION_NOT_FOUND)
    
    async def _send_message(self, action: SendMessageAction) -> AsyncIterator[Event]:
        thought_chunks: list[str] = []
        final_chunks: list[str] = []

        last_yielded_status = idle_status(action.session_id)
        final_response_started = False

        try:
            async for i, message in aenumerate(self.harness.process_input(action.text, action.session_id)):
                if i == 0:
                    yield UserMessageEvent(text=action.text, session_id=action.session_id)

                if not isinstance(message, AssistantMessage):
                    continue

                content = message.content
                thought = message.reasoning_content or message.reasoning

                if thought:
                    if last_yielded_status != thinking_status(action.session_id):
                        last_yielded_status = thinking_status(action.session_id)
                        yield last_yielded_status

                    thought_chunks.append(thought)
                    yield ThoughtChunkEvent(session_id=action.session_id, chunk=thought)
                    continue

                if content:
                    if not final_response_started and thought_chunks:
                        yield ThoughtMessageEvent(text="".join(thought_chunks), session_id=action.session_id)
                        thought_chunks.clear()

                    if last_yielded_status != responding_status(action.session_id):
                        last_yielded_status = responding_status(action.session_id)
                        yield last_yielded_status

                    final_response_started = True
                    final_chunks.append(content)
                    yield ResponseChunkEvent(session_id=action.session_id, chunk=content)
        except AgentAlreadyRunning:
            yield ErrorEvent(message=ErrorMessage.AGENT_RUNNING)
            return

        except ExecutionInterrupted:
            return

        yield AssistantMessageEvent(text="".join(final_chunks), session_id=action.session_id)
        yield idle_status(action.session_id)
    
    async def _session_list(self):
        sessions = await self.session_manager.get_session_ids()
        return SessionListEvent(sessions=sessions)
    
    async def _session_create(self):
        session = await self.session_manager.new_session()
        if session.session_id:
            return SessionCreateEvent(session_id=session.session_id)
        else:
            return ErrorEvent(message=ErrorMessage.INTERNAL_ERROR)
    
    async def _chat_history(self, action: ChatHistoryAction):
        try:
            session = await self.session_manager.load_session(action.session_id)
            return ChatHistoryEvent(messages=session.history)
        except SessionNotFound:
            return ErrorEvent(message=ErrorMessage.SESSION_NOT_FOUND)

    async def _dispatch(self, action: Action) -> AsyncIterator[Event]:
        match action:
            case SessionListAction():
                yield await self._session_list()
            case SessionCreateAction():
                yield await self._session_create()
            case SendMessageAction():
                async for event in self._send_message(action):
                    yield event
            case InterruptAction():
                async for event in self._interrupt(action):
                    yield event
            case ChatHistoryAction():
                yield await self._chat_history(action)