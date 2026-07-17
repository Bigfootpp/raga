from typing import Iterator, Optional, SupportsIndex

from shared.messages import Message, AssistantMessage

class Session:
    def __init__(self, session_id: Optional[str] = None):
        self.history = []
        self.session_id = session_id
        self._checkpoint: list[Message] = []

    def __iter__(self) -> Iterator[Message]:
        return iter(self.history)

    def __len__(self) -> int:
        return len(self.history)

    def __getitem__(self, key: SupportsIndex) -> Message:
        return self.history[key]

    def copy(self) -> "Session":
        new = Session(session_id=self.session_id)
        new.load_history(self.history.copy())
        return new

    def record(self) -> None:
        self._checkpoint = self.history.copy()

    def revert(self) -> None:
        self.history = self._checkpoint.copy()

    def load_history(self, history: list[Message]) -> None:
        self.history = history.copy()
        self._checkpoint = history.copy()

    def add_message(self, message: Message) -> None:
        self.history.append(message)

    def get_new_messages(self) -> list[Message]:
        if not self._checkpoint:
            return self.history.copy()
        return self.history[len(self._checkpoint):]

    def upsert_assistant_message(
        self,
        *,
        content: str | None = None,
        reasoning: str | None = None,
        reasoning_content: str | None = None,
        tool_calls: list | None = None,
    ) -> AssistantMessage:
        if self.history and isinstance(self.history[-1], AssistantMessage):
            msg = self.history[-1]
            updated = AssistantMessage(
                content=content if content is not None else msg.content,
                reasoning=reasoning if reasoning is not None else msg.reasoning,
                reasoning_content=(
                    reasoning_content
                    if reasoning_content is not None
                    else reasoning
                    if reasoning is not None
                    else msg.reasoning_content
                ),
                tool_calls=tool_calls if tool_calls is not None else msg.tool_calls,
            )
            self.history[-1] = updated
            return updated

        new_msg = AssistantMessage(
            content=content,
            reasoning=reasoning,
            reasoning_content=reasoning_content if reasoning_content is not None else reasoning,
            tool_calls=tool_calls,
        )
        self.add_message(new_msg)
        return new_msg

    def pop(self, index: SupportsIndex = -1) -> Message:
        return self.history.pop(index)