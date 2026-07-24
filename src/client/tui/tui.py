import asyncio
import time
from typing import ClassVar

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, ScrollableContainer
from textual.css.query import NoMatches
from textual.events import Key
from textual.widgets import Input, ListView, Static

from agent_core.session import Session
from agent_core.session_manager import SessionNotFound
from client.client import AgentNotRunningError, AgentRunningError, Client
from client.tui.widgets import InfoBox, InputRow, MessageHistory, SessionList
from shared.messages import AssistantMessage, UserMessage
from utils import async_utils

INTERRUPT_THRESHOLD = 0.5


class TUI(Client, App):
    CSS_PATH = "tui.tcss"

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("ctrl+t", "toggle_session_list", "Toggle Sessions"),
        Binding("escape", "interrupt_or_close_session_list", "Interrupt/Close"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.status_lock = asyncio.Lock()
        self.feedback_lock = asyncio.Lock()
        self.session: Session = Session()
        self.last_escape_time = 0.0
        self._session_list_visible = False

    def _get_feedback_banner(self) -> Static | None:
        try:
            return self.query_one("#feedback-banner", Static)
        except NoMatches:
            return None

    def _get_status_widget(self) -> Static | None:
        try:
            return self.query_one("#status-metrics", Static)
        except NoMatches:
            return None

    def _get_message_history_widget(self) -> MessageHistory | None:
        try:
            return self.query_one("#message-history", MessageHistory)
        except NoMatches:
            return None

    def _get_scroll_container(self) -> ScrollableContainer | None:
        try:
            return self.query_one("#main-scroll", ScrollableContainer)
        except NoMatches:
            return None

    def _get_session_list_widget(self) -> SessionList | None:
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

    async def on_key(self, event: Key) -> None:
        if event.key == "escape":
            current_time = time.time()
            if current_time - self.last_escape_time < INTERRUPT_THRESHOLD:
                await self.interrupt_current_session()
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
            await self.interrupt_current_session()

    async def interrupt_current_session(self) -> None:
        if self.session.session_id:
            try:
                await super().interrupt(self.session.session_id)
                self.session.revert()
                self.update_history(self.session)
                self.set_status("interrupted", lock_duration=2)
            except (AgentNotRunningError, SessionNotFound):
                pass

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if item and hasattr(item, 'session_id'):
            session_id: str | None = getattr(item, "session_id", None)
            if session_id:
                await self.select_session(session_id)

    async def load_session(self, session_id: str) -> None:
        history = await self.load_chat_history(session_id)
        self.session = Session(session_id=session_id)
        self.session.load_history(history)
        self.session.record()
        self.update_history(self.session)

    async def select_session(self, session_id: str) -> None:
        await self.load_session(session_id)
        self.hide_session_list()

    async def handle_disconnect(self) -> None:
        print("Disconnected")
        self.set_status("disconnected")

    async def handle_connect(self) -> None:
        print("Connected")
        self.set_status("connected")

    def upsert_assistant_message(self, *, content: str | None = None, reasoning: str | None = None) -> None:
        if content is None and reasoning is None:
            return

        self.session.upsert_assistant_message(content=content, reasoning=reasoning)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()

        if not text:
            return

        if not self.connected:
            self.show_feedback("Not connected", duration=2)
            event.input.value = ""
            return

        event.input.value = ""
        self.process_stream(text)

    @work()
    async def process_stream(self, text: str):
        try:
            if not self.session.session_id:
                session_id = await self.create_session()
                self.session = Session(session_id=session_id)
                assert self.session.session_id is not None # type check

            current_response = ""
            current_reasoning = ""

            self.session.add_message(UserMessage(content=text))
            self.session.record()
            self.update_history(self.session)

            try:
                async for chunk in self.process_input(self.session.session_id, text):
                    if not isinstance(chunk, AssistantMessage):
                        continue
                    current_response += chunk.content or ""
                    current_reasoning += chunk.reasoning_content or ""
                    self.upsert_assistant_message(content=current_response, reasoning=current_reasoning)
                    self.update_history(self.session)
            except SessionNotFound:
                self.show_feedback("Session not found")
            except AgentRunningError:
                self.show_feedback("Agent already running")

            self.session.record()
            self.update_history(self.session)

        except ConnectionError:
            self.show_feedback("Connection lost", duration=2)
        except ValueError as e:
            self.show_feedback(str(e), duration=2)

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