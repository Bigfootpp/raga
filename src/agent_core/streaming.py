import asyncio
from typing import AsyncIterator
from shared.messages import AssistantMessage, Message

MOCK_WAIT_TIME = 0.3

MOCK_THINKING = "Thinking about testing"
MOCK_RESPONSE = "This is a test"

# Mock stream class
class Stream:
    async def __aiter__(self) -> AsyncIterator[Message]:
        for text, reasoning in (
            (MOCK_THINKING, True),
            (MOCK_RESPONSE, False),
        ):
            for i, text in enumerate(text.split(" ")):
                await asyncio.sleep(MOCK_WAIT_TIME)

                chunk = text if i == 0 else " " + text
                
                if reasoning:
                    yield AssistantMessage(
                        reasoning=chunk,
                        reasoning_content=chunk
                    )
                else:
                    yield AssistantMessage(
                        content=chunk
                    )