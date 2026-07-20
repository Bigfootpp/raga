import asyncio
from typing import AsyncIterator, Optional

from agent_core.agent import Agent
from agent_core.session_manager import SessionManager
from shared.messages import AssistantMessage, Message, UserMessage

class AgentAlreadyRunning(Exception):
    pass

class AgentNotRunning(Exception):
    pass

class ExecutionInterrupted(Exception):
    pass

class Harness:
    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager
        self.session_locks: dict[str, asyncio.Lock] = {}
        self._session_tasks: dict[str, Optional[asyncio.Task]] = {}
    
    async def interrupt(self, session_id: str):
        task = self._session_tasks.get(session_id)
        if task is None or task.done():
            raise AgentNotRunning("Agent is not running")
        
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def process_input(self, input: str, session_id: str) -> AsyncIterator[Message]:
        if not input or not input.strip():
            return
        
        session = await self.session_manager.load_session(session_id)
        agent = Agent(session)
        lock = self.session_locks.get(session_id)
        if lock is None:
            lock = asyncio.Lock()
            self.session_locks[session_id] = lock

        if lock.locked():
            raise AgentAlreadyRunning("Agent is already running")

        async with lock:
            self._session_tasks[session_id] = asyncio.current_task()

            thinking_chunks: list[str] = []
            final_chunks: list[str] = []

            session.add_message(UserMessage(content=input))
            await self.session_manager.persist_turn(session)
            try:
                async for chunk in await agent.run():
                    if isinstance(chunk, AssistantMessage):
                        content = chunk.content
                        thought = chunk.reasoning_content or chunk.reasoning
                        if content:
                            final_chunks.append(content)
                        elif thought:
                            thinking_chunks.append(thought)
                        
                    yield chunk                

                if thinking_chunks or final_chunks:
                    session.add_message(AssistantMessage(
                        reasoning_content="".join(thinking_chunks) if thinking_chunks else None,
                        reasoning="".join(thinking_chunks) if thinking_chunks else None,
                        content="".join(final_chunks) if final_chunks else None
                    ))
            except asyncio.CancelledError:
                session.revert()
                raise ExecutionInterrupted("The execution was canceled")
            except Exception:
                session.revert()
                raise
            else:
                await self.session_manager.persist_turn(session)
            finally:
                self._session_tasks.pop(session_id, None)
                self.session_locks.pop(session_id, None)