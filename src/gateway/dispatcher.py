from typing import AsyncIterator

from agent_core.harness import Harness
from utils.frames import (
    Action,
    Event,
    SendMessageAction,
    StatusEvent,
    ResponseChunkEvent,
    ThoughtChunkEvent,
    StatusType,
    UserMessageEvent,
)

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

    async def dispatch(self, action: Action) -> AsyncIterator[Event]:
        match action:
            case SendMessageAction():
                last_yielded_status = idle_status
                
                yield UserMessageEvent(text=action.text)
                
                async for event in await self.harness.process_input(action.text):
                    status_for_event = EVENT_STATUS_MAPPING[event.__class__]
                
                    if status_for_event != last_yielded_status:
                        last_yielded_status = status_for_event
                        yield last_yielded_status
                    
                    yield event
                
                yield idle_status