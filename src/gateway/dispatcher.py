from typing import AsyncIterator

from agent_core.harness import Harness
from utils.events import Event, StatusEvent, ResponseChunkEvent, ThoughtChunkEvent

idle_status = StatusEvent("idle")
responding_status = StatusEvent("responding")
thinking_status = StatusEvent("thinking")

EVENT_STATUS_MAPPING: dict[type[Event], StatusEvent] = {
    ResponseChunkEvent: responding_status,
    ThoughtChunkEvent: thinking_status
}

class Dispatcher:
    def __init__(self):
        self.harness = Harness()

    async def dispatch(self, message: Event) -> AsyncIterator[Event]:
        match message.type:
            case "send_message":
                status = idle_status
                async for event in await self.harness.process_input(message.data["text"]):
                    current_status = EVENT_STATUS_MAPPING[event.__class__]
                    if current_status != status:
                        status = current_status
                        yield current_status
                    yield event
                yield idle_status