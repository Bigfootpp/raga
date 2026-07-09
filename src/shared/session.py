from typing import Iterator, SupportsIndex

from shared.messages import Message

class Session:
    def __init__(self, history: list[Message]):
        self.history = history
        self.state = []
    
    def __iter__(self) -> Iterator[Message]:
        return iter(self.history)
    
    def __len__(self):
        return len(self.history)

    def __getitem__(self, key) -> Message:
        return self.history[key]
    
    def copy(self):
        self_copy = Session(history=self.history.copy())
        self.state = self.history.copy()
        return self_copy

    def save_state(self):
        self.state = self.history.copy()
    
    def load_state(self):
        self.history = self.state.copy()

    def load_history(self, history: list[Message]):
        self.history = history
    
    def add_message(self, message: Message):
        self.history.append(message)
    
    def pop(self, index: SupportsIndex = -1) -> Message:
        return self.history.pop(index)