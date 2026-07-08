import asyncio
from typing import AsyncIterator, Optional

from agent_core.agent import Agent
from agent_core.session import Session, UserContent
from utils.frames import Event

class AgentBusyError(Exception):
    pass

class AgentNotBusyError(Exception):
    pass

class Harness:
    def __init__(self):
        self.session = Session([])
        self.agent = Agent(self.session)
        self.lock = asyncio.Lock()
        self._current_task: Optional[asyncio.Task] = None
    
    async def interrupt(self):
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()

    async def process_input(self, input: str) -> AsyncIterator[Event]:
        if self.lock.locked():
            raise AgentBusyError("Agent is busy")

        async with self.lock:
            self._current_task = asyncio.current_task()

            self.session.save_state()
            self.session.add_message(UserContent(input))
            try:
                async for event in await self.agent.run():
                    yield event
            except asyncio.CancelledError:
                self.session.load_state()
                raise
            finally:
                self._current_task = None