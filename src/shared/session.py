from typing import Iterator, SupportsIndex

from shared.messages import AssistantMessage, Message


class Session:
    def __init__(self):
        self.history = []
        self.state: list[Message] = []

    def __iter__(self) -> Iterator[Message]:
        return iter(self.history)

    def __len__(self) -> int:
        return len(self.history)

    def __getitem__(self, key: SupportsIndex) -> Message:
        return self.history[key]

    def copy(self) -> "Session":
        self_copy = Session()
        self_copy.load_history(self.history.copy())
        self.state = self.history.copy()
        return self_copy

    def record(self) -> None:
        self.state = self.history.copy()

    def revert(self) -> None:
        self.history = self.state.copy()

    def load_history(self, history: list[Message]) -> None:
        self.history = history.copy()
        self.state = history.copy()

    def add_message(self, message: Message) -> None:
        self.history.append(message)

    def upsert_assistant_message(
        self,
        *,
        content: str | None = None,
        reasoning: str | None = None,
        reasoning_content: str | None = None,
        tool_calls: list | None = None,
    ) -> AssistantMessage:
        if self.history and isinstance(self.history[-1], AssistantMessage):
            assistant_message = self.history[-1]
            updated_message = AssistantMessage(
                content=content if content is not None else assistant_message.content,
                reasoning=reasoning if reasoning is not None else assistant_message.reasoning,
                reasoning_content=(
                    reasoning_content
                    if reasoning_content is not None
                    else reasoning
                    if reasoning is not None
                    else assistant_message.reasoning_content
                ),
                tool_calls=tool_calls if tool_calls is not None else assistant_message.tool_calls,
            )
            self.history[-1] = updated_message
            return updated_message

        new_message = AssistantMessage(
            content=content,
            reasoning=reasoning,
            reasoning_content=reasoning_content if reasoning_content is not None else reasoning,
            tool_calls=tool_calls,
        )
        self.add_message(new_message)
        return new_message

    def pop(self, index: SupportsIndex = -1) -> Message:
        return self.history.pop(index)