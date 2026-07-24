from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Input, Label, ListItem, ListView, Static

from agent_core.session import Session
from shared.messages import AssistantMessage, UserMessage

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


class ThinkingMessageContainer(Container):
    def __init__(self, text: str, **kwargs) -> None:
        super().__init__(classes="thinking-container", **kwargs)
        self.text = text

    def compose(self) -> ComposeResult:
        header = Static(classes="thinking-header")
        header.border_title = "thinking"
        yield header
        yield Label(self.text, classes="thinking-content")


class AgentMessageContainer(Container):
    def __init__(self, text: str, **kwargs) -> None:
        super().__init__(classes="message-box", **kwargs)
        self.text = text

    def compose(self) -> ComposeResult:
        yield Label("AGENT", classes="agent-message-sender")
        yield Label(self.text, classes="agent-message-content")


class SessionItem(ListItem):
    def __init__(self, session_id: str, title: str = "", **kwargs):
        super().__init__(**kwargs)
        self.session_id = session_id
        self.title = title or session_id[:8] + "..."

    def compose(self) -> ComposeResult:
        yield Label(self.title, classes="session-item-title")


class SessionList(Container):
    def __init__(self, id="session-list", **kwargs):
        super().__init__(id=id, **kwargs)
        self.styles.display = "none"

    def compose(self) -> ComposeResult:
        yield Label("Sessions", classes="session-list-title")
        yield ListView(id="session-list-view")
        yield Label("\u2191\u2193 navigate \u2022 Enter select \u2022 Esc close", classes="session-list-hint")

    def populate(self, sessions: list[str]) -> None:
        list_view = self.query_one("#session-list-view", ListView)
        list_view.clear()
        for session_id in sessions:
            list_view.append(SessionItem(session_id))

    def get_selected_session_id(self) -> str | None:
        list_view = self.query_one("#session-list-view", ListView)
        highlighted_child = list_view.highlighted_child
        if highlighted_child:
            session_id = getattr(highlighted_child, "session_id", None)
            if session_id is not None:
                return session_id
        return None

    def show_list(self) -> None:
        self.styles.display = "block"
        self.query_one("#session-list-view", ListView).focus()

    def hide_list(self) -> None:
        self.styles.display = "none"


class MessageHistory(Container):
    def __init__(self, id="message-history", **kwargs):
        super().__init__(id=id, **kwargs)

    def update_history(self, history_list: Session) -> None:
        for queried in (
            self.query(UserMessageContainer),
            self.query(AgentMessageContainer),
            self.query(ThinkingMessageContainer),
        ):
            for message_widget in queried:
                message_widget.remove()

        for message in history_list:
            match message:
                case UserMessage():
                    self.mount(UserMessageContainer(message.content))
                case AssistantMessage():
                    content = message.content
                    reasoning = message.reasoning_content
                    if reasoning:
                        self.mount(ThinkingMessageContainer(reasoning))
                    if content:
                        self.mount(AgentMessageContainer(content))


class InputRow(Horizontal):
    def compose(self) -> ComposeResult:
        yield Static("> ", id="prompt-char")
        yield Input(placeholder="Ask RAGA something...", id="user-input").focus()