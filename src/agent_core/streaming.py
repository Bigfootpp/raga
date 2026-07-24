import asyncio
from collections.abc import AsyncIterator

from shared.messages import AssistantMessage, MessageUnion

MOCK_WAIT_TIME = 0.3

MOCK_THINKING = "Thinking about testing"
MOCK_RESPONSE = "This is a test"

# Mock stream class
class Stream:
    async def __aiter__(self) -> AsyncIterator[MessageUnion]:
        for text, reasoning in (
            (MOCK_THINKING, True),
            (MOCK_RESPONSE, False),
        ):
            for i, chunk in enumerate(text.split(" ")):
                await asyncio.sleep(MOCK_WAIT_TIME)

                chunk = chunk if i == 0 else " " + chunk

                if reasoning:
                    yield AssistantMessage(
                        reasoning_content=chunk
                    )
                else:
                    yield AssistantMessage(
                        content=chunk
                    )