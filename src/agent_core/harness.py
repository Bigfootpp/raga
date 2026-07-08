import asyncio
from typing import AsyncIterator

from agent_core.agent import Agent
from agent_core.session import Session, UserContent
from utils.frames import Event

class AgentBusyError(Exception):
    pass

class Harness:
    def __init__(self):
        self.session = Session([])
        self.agent = Agent(self.session)
        self.lock = asyncio.Lock()
    
    async def process_input(self, input: str) -> AsyncIterator[Event]:
        if not self.lock.locked():
            async with self.lock:
                self.session.add_message(UserContent(input))
                async for event in await self.agent.run():
                    yield event
        else:
            raise AgentBusyError("Agent is busy")