import asyncio
from typing import AsyncIterator, Optional

from agent_core.agent import Agent
from agent_core.session import Session, UserContent
from utils.frames import Event

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

            self.session.save_state()
            self.session.add_message(UserContent(input))
            try:
                async for event in await self.agent.run():
                    yield event
            except asyncio.CancelledError:
                self.session.load_state()
                raise ExecutionInterrupted("The execution was canceled")
            finally:
                self._current_task = None