import asyncio
from typing import AsyncIterator
from shared.frames import Event, ResponseChunkEvent, ThoughtChunkEvent

MOCK_WAIT_TIME = 0.3

MOCK_THINKING = "Thinking about testing"
MOCK_RESPONSE = "This is a test"

# Mock stream class
class Stream:
    async def __aiter__(self) -> AsyncIterator[Event]:
        for text, event_cls in (
            (MOCK_THINKING, ThoughtChunkEvent),
            (MOCK_RESPONSE, ResponseChunkEvent),
        ):
            for i, chunk in enumerate(text.split(" ")):
                await asyncio.sleep(MOCK_WAIT_TIME)
                if i == 0:
                    yield event_cls(chunk=chunk)
                else:
                    yield event_cls(chunk=" " + chunk)