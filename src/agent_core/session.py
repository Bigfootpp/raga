class Message:
    pass

class UserMessage(Message):
    def __init__(self, input: str):
        self.input = input

class ThoughtMessage(Message):
    def __init__(self, input: str):
        self.input = input

class AgentMessage(Message):
    def __init__(self, input: str):
        self.input = input

class Session:
    def __init__(self, history: list[Message]):
        self.history = history
        self.state = []
    
    def save_state(self):
        self.state = self.history.copy()
    
    def load_state(self):
        self.history = self.state.copy()

    def load_history(self, history: list[Message]):
        self.history = history
    
    def add_message(self, message: Message):
        self.history.append(message)