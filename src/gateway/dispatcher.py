from typing import AsyncIterator

from agent_core.harness import Harness
from utils.frames import (
    Action,
    AssistantMessageEvent,
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
                final_message = ""

                last_yielded_status = idle_status
                
                yield UserMessageEvent(text=action.text)
                
                async for event in await self.harness.process_input(action.text):
                    status = EVENT_STATUS_MAPPING[event.__class__]
                
                    if status != last_yielded_status:
                        last_yielded_status = status
                        yield last_yielded_status
                    
                    if isinstance(event, ResponseChunkEvent):
                        final_message += event.chunk
                    
                    yield event
                
                yield AssistantMessageEvent(text=final_message)
                yield idle_status