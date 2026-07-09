from shared.messages import Message

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