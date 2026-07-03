from typing import AsyncIterator

from agent_core.harness import Harness
from utils.messages import Action, Event, SendMessageAction, StatusEvent, ResponseChunkEvent, ThoughtChunkEvent, StatusType

idle_status = StatusEvent(state=StatusType.IDLE)
responding_status = StatusEvent(state=StatusType.RESPONDING)
thinking_status = StatusEvent(state=StatusType.THINKING)

EVENT_STATUS_MAPPING: dict[type[Event], StatusEvent] = {
    ResponseChunkEvent: responding_status,
    ThoughtChunkEvent: thinking_status
}

class Dispatcher:
    def __init__(self):
        self.harness = Harness()

    async def dispatch(self, message: Action) -> AsyncIterator[Event]:
        match message:
            case SendMessageAction():
                status = idle_status
                async for event in await self.harness.process_input(message.text):
                    current_status = EVENT_STATUS_MAPPING[event.__class__]
                    if current_status != status:
                        status = current_status
                        yield current_status
                    yield event
                yield idle_status