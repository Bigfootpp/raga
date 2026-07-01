from typing import AsyncIterator

from agent_core.harness import Harness
from agent_core.streaming import Event

class Dispatcher:
    def __init__(self):
        self.harness = Harness()

    async def dispatch(self, message: Event) -> AsyncIterator[Event]:
        match message.type:
            case "send_message":
                async for event in await self.harness.process_input(message.data["text"]):
                    yield event