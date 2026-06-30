class Message:
    def __init__(self, role: str, input: str):
        self.role = role
        self.input = input
    
    def to_dict(self):
        return {
            "role": self.role,
            "content": self.input
        }

class UserContent(Message):
    def __init__(self, input: str):
        super().__init__("user", input)

class AgentContent(Message):
    def __init__(self, input: str):
        super().__init__("assistant", input)

class Session:
    def __init__(self, history: list[Message]):
        self.history = history
    
    def load_history(self, history: list[Message]):
        self.history = history
    
    def add_message(self, message: Message):
        self.history.append(message)