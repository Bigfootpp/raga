from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import Input, Static, Label

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

class UserMessage(Container):
    def __init__(self, text: str, **kwargs) -> None:
        super().__init__(classes="message-box", **kwargs)
        self.text = text

    def compose(self) -> ComposeResult:
        yield Label("USER", classes="user-message-sender")
        yield Label(self.text, classes="user-message-content")

class AgentMessage(Container):
    def __init__(self, text: str, **kwargs) -> None:
        super().__init__(classes="message-box", **kwargs)
        self.text = text

    def compose(self) -> ComposeResult:
        yield Label("AGENT", classes="agent-message-sender")
        yield Label(self.text, classes="agent-message-content")

class MessageHistory(Container):
    def __init__(self, id="message-history", **kwargs):
        super().__init__(id=id, **kwargs)

    def update_history(self, history_list: list[str]) -> None:
        for message_widget in self.query(UserMessage):
            message_widget.remove()

        for message_widget in self.query(AgentMessage):
            message_widget.remove()

        for text in history_list:
            self.mount(UserMessage(text))
            self.mount(AgentMessage(text))
    
class InputRow(Horizontal):
    def compose(self) -> ComposeResult:
        yield Static("> ", id="prompt-char")
        yield Input(placeholder="Ask RAGA something...", id="user-input").focus()

class RagaTUI(App):
    history: list[str] = []
    CSS_PATH = "tui.tcss"

    def compose(self) -> ComposeResult:
        with ScrollableContainer(id="main-scroll"):
            yield InfoBox()
            yield MessageHistory()
        with Horizontal(id="status-bar"):
            yield Static(" ⎈ RAGA ", id="status-badge")
            yield Static(" TODO", id="status-metrics") # Prototype design: (ctx --  |  [░░░░░░░░░░]  |  14s  |  🌐 0s)
        yield InputRow(id="input-row")
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()

        if not text:
            return

        self.history.append(text)

        history = self.query_one("#message-history", MessageHistory)
        history.update_history(self.history)

        event.input.value = ""

        scroll = self.query_one("#main-scroll", ScrollableContainer)
        scroll.scroll_end(animate=False)

if __name__ == "__main__":
    app = RagaTUI()
    app.run()