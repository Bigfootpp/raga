from shared.session import Session
from agent_core.streaming import Stream

class Agent:
    def __init__(self, session: Session):
        self.session = session
    
    async def run(self) -> Stream:
        return Stream()