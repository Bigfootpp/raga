from typing import AsyncIterator

from agent_core.harness import AgentAlreadyRunning, AgentNotRunning, ExecutionInterrupted, Harness
from utils.async_utils import aenumerate
from utils.frames import (
    Action,
    AssistantMessageEvent,
    ErrorEvent,
    ErrorMessage,
    Event,
    InterruptAction,
    InterruptedEvent,
    SendMessageAction,
    StatusEvent,
    ResponseChunkEvent,
    ThoughtChunkEvent,
    StatusType,
    ThoughtMessageEvent,
    UserMessageEvent,
)

IDLE_STATUS = StatusEvent(state=StatusType.IDLE)
RESPONDING_STATUS = StatusEvent(state=StatusType.RESPONDING)
THINKING_STATUS = StatusEvent(state=StatusType.THINKING)

EVENT_STATUS_MAPPING: dict[type[Event], StatusEvent] = {
    ResponseChunkEvent: RESPONDING_STATUS,
    ThoughtChunkEvent: THINKING_STATUS,
}


class Dispatcher:
    def __init__(self) -> None:
        self.harness = Harness()
    
    async def _hande_interrupt(self):
        try:
            await self.harness.interrupt()
            yield InterruptedEvent()
            yield IDLE_STATUS
        except AgentNotRunning:
            yield ErrorEvent(message=ErrorMessage.AGENT_NOT_RUNNING)
    
    async def _handle_send_message(self, action: SendMessageAction) -> AsyncIterator[Event]:
        thinking_chunks: list[str] = []
        final_chunks: list[str] = []

        last_yielded_status = IDLE_STATUS

        try:
            async for i, event in aenumerate(self.harness.process_input(action.text)):
                if i == 0:
                    yield UserMessageEvent(text=action.text)
                
                status = EVENT_STATUS_MAPPING.get(type(event))
            
                if status is not None and status != last_yielded_status:
                    if last_yielded_status == THINKING_STATUS and status == RESPONDING_STATUS:
                        if thinking_chunks:
                            yield ThoughtMessageEvent(text="".join(thinking_chunks))
                    elif last_yielded_status == RESPONDING_STATUS and status == THINKING_STATUS:
                        if final_chunks:
                            yield AssistantMessageEvent(text="".join(final_chunks))
                    
                    last_yielded_status = status
                    yield last_yielded_status
                
                if isinstance(event, ResponseChunkEvent):
                    final_chunks.append(event.chunk)
                elif isinstance(event, ThoughtChunkEvent):
                    thinking_chunks.append(event.chunk)

                yield event
        except AgentAlreadyRunning:
            yield ErrorEvent(message=ErrorMessage.AGENT_RUNNING)
            return
        
        except ExecutionInterrupted:
            return
        
        yield AssistantMessageEvent(text="".join(final_chunks))
        yield IDLE_STATUS

    async def dispatch(self, action: Action) -> AsyncIterator[Event]:
        match action:
            case SendMessageAction():
                async for event in self._handle_send_message(action):
                    yield event
            case InterruptAction():
                async for event in self._hande_interrupt():
                    yield event