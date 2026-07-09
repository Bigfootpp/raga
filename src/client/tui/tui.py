import asyncio
import time
from typing import Optional

from client.client import Client
from client.tui.widgets import InfoBox, InputRow, MessageHistory
from shared.messages import UserMessage
from shared.session import Session
from textual.app import App, ComposeResult
from textual.containers import Horizontal, ScrollableContainer
from textual.css.query import NoMatches
from textual.events import Key
from textual.widgets import Input, Static
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
)
from utils import async_utils

INTERRUPT_THRESHOLD = 0.5

class TUI(Client, App):
    CSS_PATH = "tui.tcss"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_response = ""
        self.current_reasoning = ""
        self.status_lock = asyncio.Lock()
        self.feedback_lock = asyncio.Lock()
        self.session: Session = Session([])
        self.last_escape_time = 0.0

    def reset_streaming_state(self) -> None:
        self.current_response = ""
        self.current_reasoning = ""
    
    @async_utils.background_task
    async def show_feedback(self, message: str, *, duration: float = 1) -> None:
        try:
            banner = self.query_one("#feedback-banner", Static)
        except NoMatches:
            return

        async with self.feedback_lock:
            banner.update(message)
            banner.styles.display = "block"
            await asyncio.sleep(duration)
            await self._hide_feedback()
    
    async def _hide_feedback(self) -> None:
        try:
            banner = self.query_one("#feedback-banner", Static)
        except NoMatches:
            return

        banner.update("")
        banner.styles.display = "none"
    
    @async_utils.background_task
    async def set_status(self, text: str, lock_duration: int = 0):
        async with self.status_lock:
            try:
                status_widget = self.query_one("#status-metrics", Static)
            except NoMatches:
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
        yield Static("", id="feedback-banner")
        with Horizontal(id="status-bar"): # Prototype design: (ctx --  |  [░░░░░░░░░░]  |  14s  |  🌐 0s)
            yield Static(" ⎈ RAGA ", id="status-badge")
            yield Static("label", id="status-metrics")
        yield InputRow(id="input-row")
    
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()

        if not text:
            return
        
        try:
            await self.process_input(text)
        except ConnectionError:
            pass

        event.input.value = ""
    
    async def on_key(self, event: Key) -> None:
        if event.key == "escape":
            current_time = time.time()
            if current_time - self.last_escape_time < INTERRUPT_THRESHOLD:
                await self.interrupt()
                self.last_escape_time = 0.0
            else:
                self.last_escape_time = current_time

    async def interrupt(self) -> None:
        try:
            await super().interrupt()
        except ConnectionError:
            pass
    
    async def handle_disconnect(self) -> None:
        self.log("Disconnected")
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
        self.session.save_state()
        self.update_history(self.session)
        self.reset_streaming_state()
    
    async def handle_assistant_message(self, event: AssistantMessageEvent) -> None:
        self.log(event.text)

        self.current_response = event.text
        self.upsert_assistant_message(content=self.current_response)
        self.session.save_state()
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
        self.set_status(f"status: {event.state}")
    
    async def handle_error(self, event: ErrorEvent) -> None:
        self.log(event.message)

        if event.message == ErrorMessage.AGENT_RUNNING:
            self.show_feedback(ErrorMessage.AGENT_RUNNING)
    
    async def handle_interrupted(self, event: InterruptedEvent) -> None:
        self.session.load_state()
        self.update_history(self.session)
        self.reset_streaming_state()
        self.set_status("interrupted", lock_duration=2)
    
    def update_history(self, history_list: Session) -> None:
        session = self.query_one("#message-history", MessageHistory)
        session.update_history(history_list)

        scroll = self.query_one("#main-scroll", ScrollableContainer)
        scroll.scroll_end(animate=False)

if __name__ == "__main__":
    app = TUI()
    app.run()