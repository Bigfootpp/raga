from client.client import Client
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import Input, Static, Label
from utils.frames import (
    AssistantMessageEvent,
    ErrorEvent,
    ResponseChunkEvent,
    StatusEvent,
    ThoughtChunkEvent,
    UserMessageEvent,
)
from utils.messages import AssistantMessage, Message, UserMessage

LOGO = r"""
                 .                      
                 )@@B                   
          +U'    .8%x      .'           
         p@@B^. ..)d" .  1B$@.          
          .;^MWBI. 0  |%_#-W^           
            ]w]U'  m . &:@.             
         ' "L'  /|.@ W'  .%  ..         
     .B$@d.0_:^.:(@@$l^.'la: B@@?       
      ]BB` /n    z#%('.  .@  r%o        
            B` -c  0 .%  O\             
            'h0    Z    %^  .           
         !BB%  <@%a#&@a  'BBd           
         "BB%      O.    ~8@%           
                 ]@@8                   
                  BBq                                                                              
"""

class InfoBox(Container):
    def __init__(self, id="info-box", **kwargs):
        super().__init__(id=id, **kwargs)

    def compose(self) -> ComposeResult:
        self.border_title = "RAGA - Adaptive agent"
        with Vertical(id="left-pane"):
            yield Static(LOGO, id="logo")
            yield Label("RAGA - Adaptive agent", classes="meta-title")
        with Vertical(id="right-pane"):
            yield Label("Available Tools", classes="section-title")

class UserMessageContainer(Container):
    def __init__(self, text: str, **kwargs) -> None:
        super().__init__(classes="message-box", **kwargs)
        self.text = text

    def compose(self) -> ComposeResult:
        yield Label("USER", classes="user-message-sender")
        yield Label(self.text, classes="user-message-content")

class AgentMessageContainer(Container):
    def __init__(self, text: str, **kwargs) -> None:
        super().__init__(classes="message-box", **kwargs)
        self.text = text

    def compose(self) -> ComposeResult:
        yield Label("AGENT", classes="agent-message-sender")
        yield Label(self.text, classes="agent-message-content")

class MessageHistory(Container):
    def __init__(self, id="message-history", **kwargs):
        super().__init__(id=id, **kwargs)

    def update_history(self, history_list: list[Message]) -> None:
        for message_widget in self.query(UserMessageContainer):
            message_widget.remove()

        for message_widget in self.query(AgentMessageContainer):
            message_widget.remove()

        for message in history_list:
            match message:
                case UserMessage():
                    self.mount(UserMessageContainer(message.content))
                case AssistantMessage():
                    if message.content:
                        self.mount(AgentMessageContainer(message.content))

class InputRow(Horizontal):
    def compose(self) -> ComposeResult:
        yield Static("> ", id="prompt-char")
        yield Input(placeholder="Ask RAGA something...", id="user-input").focus()

class TUI(Client, App):
    CSS_PATH = "tui.tcss"

    current_response = ""

    history: list[Message] = []
    async def on_mount(self):
        await self.connect()

    def compose(self) -> ComposeResult:
        with ScrollableContainer(id="main-scroll"):
            yield InfoBox()
            yield MessageHistory()
        with Horizontal(id="status-bar"):
            yield Static(" ⎈ RAGA ", id="status-badge")
            yield Static(" TODO", id="status-metrics") # Prototype design: (ctx --  |  [░░░░░░░░░░]  |  14s  |  🌐 0s)
        yield InputRow(id="input-row")
    
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()

        if not text:
            return
        
        await self.process_input(text)

        self.current_response = ""

        event.input.value = ""
    
    async def handle_response(self, event: ResponseChunkEvent) -> None:
        self.log(event.chunk)

        self.current_response = self.current_response + event.chunk
        
        history_copy = self.history.copy()
        history_copy.append(AssistantMessage(content=self.current_response))
        self.update_history(history_copy)
    
    async def handle_user_message(self, event: UserMessageEvent) -> None:
        self.log(event.text)

        self.history.append(UserMessage(content=event.text))
        self.update_history(self.history)
    
    async def handle_assistant_message(self, event: AssistantMessageEvent) -> None:
        self.log(event.text)

        self.history.append(AssistantMessage(content=event.text))
        self.update_history(self.history)
        
        self.current_response = ""
    
    async def handle_status(self, event: StatusEvent) -> None:
        self.log(event.state)
    
    async def handle_thought(self, event: ThoughtChunkEvent) -> None:
        self.log(event.chunk)
    
    async def handle_disconnect(self) -> None:
        self.log("Disconnected")
    
    async def handle_connect(self) -> None:
        self.log("Connected")
    
    async def handle_error(self, event: ErrorEvent) -> None:
        self.log(event.message)
    
    def update_history(self, history_list: list[Message]):
        history = self.query_one("#message-history", MessageHistory)
        history.update_history(history_list)

        scroll = self.query_one("#main-scroll", ScrollableContainer)
        scroll.scroll_end(animate=False)

if __name__ == "__main__":
    app = TUI()
    app.run()