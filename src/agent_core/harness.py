from agent_core.agent import Agent
from agent_core.session import Session, UserContent
from agent_core.streaming import Stream


class Harness:
    def __init__(self):
        self.session = Session([])
        self.agent = Agent(self.session)
    
    async def process_input(self, input: str) -> Stream:
        self.session.add_message(UserContent(input))
        return await self.agent.run()