import asyncio
import time
from typing import Optional

from client.client import Client
from client.tui.widgets import InfoBox, InputRow, MessageHistory, SessionList
from shared.messages import UserMessage
from agent_core.session import Session
from textual.app import App, ComposeResult
from textual.containers import Horizontal, ScrollableContainer
from textual.css.query import NoMatches
from textual.events import Key
from textual.widgets import Input, Static, ListView
from shared.frames import (
    AssistantMessageEvent,
    ErrorEvent,
    ErrorMessage,
    InterruptedEvent,
    ResponseChunkEvent,
    StatusEvent,
    ThoughtChunkEvent,
    ThoughtMessageEvent,
    UserMessageEvent,
    SessionCreateEvent,
)
from utils import async_utils

INTERRUPT_THRESHOLD = 0.5


class TUI(Client, App):
    CSS_PATH = "tui.tcss"

    BINDINGS = [
        ("ctrl+t", "toggle_session_list", "Toggle Sessions"),
        ("escape", "interrupt_or_close_session_list", "Interrupt/Close"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_response = ""
        self.current_reasoning = ""
        self.status_lock = asyncio.Lock()
        self.feedback_lock = asyncio.Lock()
        self.session: Session = Session()
        self.last_escape_time = 0.0
        self._session_list_visible = False

    def reset_streaming_state(self) -> None:
        self.current_response = ""
        self.current_reasoning = ""
    
    def _get_feedback_banner(self) -> Optional[Static]:
        try:
            return self.query_one("#feedback-banner", Static)
        except NoMatches:
            return None

    def _get_status_widget(self) -> Optional[Static]:
        try:
            return self.query_one("#status-metrics", Static)
        except NoMatches:
            return None

    def _get_message_history_widget(self) -> Optional[MessageHistory]:
        try:
            return self.query_one("#message-history", MessageHistory)
        except NoMatches:
            return None

    def _get_scroll_container(self) -> Optional[ScrollableContainer]:
        try:
            return self.query_one("#main-scroll", ScrollableContainer)
        except NoMatches:
            return None

    def _get_session_list_widget(self) -> Optional[SessionList]:
        try:
            return self.query_one("#session-list", SessionList)
        except NoMatches:
            return None

    def _focus_history_widget(self) -> None:
        history_widget = self._get_message_history_widget()
        if history_widget:
            history_widget.focus()

    def hide_session_list(self) -> None:
        session_list = self._get_session_list_widget()
        if session_list is None:
            return

        session_list.hide_list()
        self._session_list_visible = False
        self._focus_history_widget()

    async def show_session_list(self) -> None:
        await self.update_session_list()
        session_list = self._get_session_list_widget()
        if session_list is None:
            return

        session_list.show_list()
        self._session_list_visible = True

    @async_utils.background_task
    async def show_feedback(self, message: str, *, duration: float = 1) -> None:
        banner = self._get_feedback_banner()
        if banner is None:
            return

        async with self.feedback_lock:
            banner.update(message)
            banner.styles.display = "block"
            await asyncio.sleep(duration)
            await self._hide_feedback()
    
    async def _hide_feedback(self) -> None:
        banner = self._get_feedback_banner()
        if banner is None:
            return

        banner.update("")
        banner.styles.display = "none"
    
    @async_utils.background_task
    async def set_status(self, text: str, lock_duration: int = 0):
        async with self.status_lock:
            status_widget = self._get_status_widget()
            if status_widget is None:
                return

            status_widget.update(text)
            await asyncio.sleep(lock_duration)

    async def on_mount(self):
        self.set_status("connecting")
        await self.connect()

    def compose(self) -> ComposeResult:
        with ScrollableContainer(id="main-scroll"):
            yield InfoBox()
            yield MessageHistory()
        yield SessionList()
        yield Static("", id="feedback-banner")
        with Horizontal(id="status-bar"):
            yield Static(" ⎈ RAGA ", id="status-badge")
            yield Static("label", id="status-metrics")
        yield InputRow(id="input-row")
    
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()

        if not text:
            return

        if not self.connected:
            self.show_feedback("Not connected", duration=2)
            event.input.value = ""
            return
        
        try:
            await self.process_input(text)
        except ConnectionError:
            self.show_feedback("Connection lost", duration=2)
        except ValueError as e:
            self.show_feedback(str(e), duration=2)

        event.input.value = ""
    
    async def on_key(self, event: Key) -> None:
        if event.key == "escape":
            current_time = time.time()
            if current_time - self.last_escape_time < INTERRUPT_THRESHOLD:
                await self.interrupt()
                self.last_escape_time = 0.0
            else:
                self.last_escape_time = current_time
                await self.action_interrupt_or_close_session_list()

    async def action_toggle_session_list(self) -> None:
        if self._session_list_visible:
            self.hide_session_list()
        else:
            await self.show_session_list()

    async def action_interrupt_or_close_session_list(self) -> None:
        if self._session_list_visible:
            self.hide_session_list()
        else:
            await self.interrupt()
    
    async def interrupt(self) -> None:
        try:
            await super().interrupt()
        except ConnectionError:
            pass
    
    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if item and hasattr(item, 'session_id'):
            session_id: str = getattr(item, 'session_id')
            if session_id:
                await self.select_session(session_id)

    async def load_session(self, session_id: str) -> None:
        self.set_session(session_id)
        self.session = Session(session_id=session_id)
        history = await self.load_chat_history(session_id)
        self.session.load_history(history)
        self.session.record()
        self.update_history(self.session)

    async def select_session(self, session_id: str) -> None:
        await self.load_session(session_id)
        self.hide_session_list()
    
    async def handle_disconnect(self) -> None:
        self.log("Disconnected")
        self.reset_streaming_state()
        self.set_status("disconnected")
    
    async def handle_connect(self) -> None:
        self.log("Connected")
        self.set_status("connected")
    
    def upsert_assistant_message(self, *, content: Optional[str] = None, reasoning: Optional[str] = None) -> None:
        if content is None and reasoning is None:
            return

        self.session.upsert_assistant_message(content=content, reasoning=reasoning)

    async def handle_response(self, event: ResponseChunkEvent) -> None:
        self.log(event.chunk)

        self.current_response += event.chunk
        self.upsert_assistant_message(content=self.current_response)
        self.update_history(self.session)
    
    async def handle_thought(self, event: ThoughtChunkEvent) -> None:
        self.log(event.chunk)

        self.current_reasoning += event.chunk
        self.upsert_assistant_message(reasoning=self.current_reasoning)
        self.update_history(self.session)
    
    async def handle_user_message(self, event: UserMessageEvent) -> None:
        self.log(event.text)

        self.session.add_message(UserMessage(content=event.text))
        self.session.record()
        self.update_history(self.session)
        self.reset_streaming_state()
    
    async def handle_assistant_message(self, event: AssistantMessageEvent) -> None:
        self.log(event.text)

        self.current_response = event.text
        self.upsert_assistant_message(content=self.current_response)
        self.session.record()
        self.update_history(self.session)
        self.reset_streaming_state()
    
    async def handle_thought_message(self, event: ThoughtMessageEvent) -> None:
        self.log(event.text)

        self.current_reasoning = event.text
        self.upsert_assistant_message(reasoning=self.current_reasoning)
        self.update_history(self.session)
        self.current_response = ""
    
    async def handle_status(self, event: StatusEvent) -> None:
        self.log(event.state)
        session_info = f" [{event.session_id[:8]}]" if event.session_id else ""
        self.set_status(f"status: {event.state}{session_info}")
    
    async def handle_error(self, event: ErrorEvent) -> None:
        self.log(event.message)

        match event.message:
            case ErrorMessage.AGENT_RUNNING:
                self.show_feedback(ErrorMessage.AGENT_RUNNING, duration=2)
            case ErrorMessage.AGENT_NOT_RUNNING:
                pass
            case ErrorMessage.SESSION_NOT_FOUND:
                self.show_feedback("Session not found", duration=2)
                self.current_session_id = None
            case _:
                self.show_feedback(str(event.message), duration=2)
    
    async def handle_interrupted(self, event: InterruptedEvent) -> None:
        self.session.revert()
        self.update_history(self.session)
        self.reset_streaming_state()
        self.set_status("interrupted", lock_duration=2)

    async def handle_session_create(self, event: SessionCreateEvent) -> None:
        if event.session_id:
            self.current_session_id = event.session_id
            self.session = Session(session_id=event.session_id)
            self.show_feedback(f"Session created: {event.session_id[:8]}", duration=2)
    
    async def update_session_list(self):
        sessions = await self.list_sessions()
        session_list = self._get_session_list_widget()
        if session_list:
            session_list.populate(sessions)

    def update_history(self, history_list: Session) -> None:
        session = self._get_message_history_widget()
        if session is None:
            return

        session.update_history(history_list)

        scroll = self._get_scroll_container()
        if scroll is not None:
            scroll.scroll_end(animate=False)


if __name__ == "__main__":
    app = TUI()
    app.run()