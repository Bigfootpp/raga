import asyncio
from typing import AsyncIterator, Optional

from agent_core.agent import Agent
from shared.session import Session, ThoughtMessage, UserMessage, AgentMessage
from shared.frames import Event, ResponseChunkEvent, ThoughtChunkEvent

class AgentAlreadyRunning(Exception):
    pass

class AgentNotRunning(Exception):
    pass

class ExecutionInterrupted(Exception):
    pass

class Harness:
    def __init__(self):
        self.session = Session([])
        self.agent = Agent(self.session)
        self.lock = asyncio.Lock()
        self._current_task: Optional[asyncio.Task] = None
    
    async def interrupt(self):
        if not self._current_task or self._current_task.done():
            raise AgentNotRunning("Agent is not running")
        
        self._current_task.cancel()
        try:
            await self._current_task
        except asyncio.CancelledError:
            pass

    async def process_input(self, input: str) -> AsyncIterator[Event]:
        if self.lock.locked():
            raise AgentAlreadyRunning("Agent is already running")

        async with self.lock:
            self._current_task = asyncio.current_task()

            thinking_chunks: list[str] = []
            final_chunks: list[str] = []

            self.session.add_message(UserMessage(input))
            self.session.save_state()
            try:
                async for event in await self.agent.run():
                    if isinstance(event, ResponseChunkEvent):
                        final_chunks.append(event.chunk)
                    elif isinstance(event, ThoughtChunkEvent):
                        thinking_chunks.append(event.chunk)
                        
                    yield event

                if thinking_chunks:
                    self.session.add_message(ThoughtMessage("".join(thinking_chunks)))
                if final_chunks:
                    self.session.add_message(AgentMessage("".join(thinking_chunks)))
            except asyncio.CancelledError:
                self.session.load_state()
                raise ExecutionInterrupted("The execution was canceled")
            finally:
                self._current_task = None