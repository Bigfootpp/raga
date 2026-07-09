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
    InterruptedEvent,
    ResponseChunkEvent,
    StatusEvent,
    StatusType,
    ThoughtChunkEvent,
    ThoughtMessageEvent,
    UserMessageEvent,
)

INTERRUPT_THRESHOLD = 0.5

class TUI(Client, App):
    CSS_PATH = "tui.tcss"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_response = ""
        self.current_reasoning = ""
        self.status_lock = asyncio.Lock()
        self.session: Session = Session([])
        self.last_escape_time = 0.0

    def _set_status(self, text: str) -> None:
        try:
            status_widget = self.query_one("#status-metrics", Static)
        except NoMatches:
            return

        status_widget.update(text)

    def _reset_streaming_state(self) -> None:
        self.current_response = ""
        self.current_reasoning = ""
    
    async def set_status(self, text: str):
        async with self.status_lock:
            self._set_status(f"status: {text}")
    
    async def trigger_interrupted_status(self):
        async with self.status_lock:
            self._set_status("interrupted")
            await asyncio.sleep(2)

    def _format_status(self, state: StatusType) -> str:
        mapping = {
            StatusType.IDLE: "ready",
            StatusType.RESPONDING: "responding",
            StatusType.THINKING: "thinking",
        }
        return mapping.get(state, state.value)

    async def on_mount(self):
        await self.set_status("connecting")
        await self.connect()

    def compose(self) -> ComposeResult:
        with ScrollableContainer(id="main-scroll"):
            yield InfoBox()
            yield MessageHistory()
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
                await self.interrupt_agent()
                self.last_escape_time = 0.0
            else:
                self.last_escape_time = current_time

    async def interrupt_agent(self) -> None:
        try:
            await self.interrupt()
        except ConnectionError:
            pass
    
    async def handle_disconnect(self) -> None:
        self.log("Disconnected")
        await self.set_status("disconnected")
    
    async def handle_connect(self) -> None:
        self.log("Connected")
        await self.set_status("connected")
    
    def _upsert_assistant_message(self, *, content: Optional[str] = None, reasoning: Optional[str] = None) -> None:
        if content is None and reasoning is None:
            return

        self.session.upsert_assistant_message(content=content, reasoning=reasoning)

    async def handle_response(self, event: ResponseChunkEvent) -> None:
        self.log(event.chunk)

        self.current_response += event.chunk
        self._upsert_assistant_message(content=self.current_response)
        self.update_history(self.session)
    
    async def handle_thought(self, event: ThoughtChunkEvent) -> None:
        self.log(event.chunk)

        self.current_reasoning += event.chunk
        self._upsert_assistant_message(reasoning=self.current_reasoning)
        self.update_history(self.session)
    
    async def handle_user_message(self, event: UserMessageEvent) -> None:
        self.log(event.text)

        self.session.add_message(UserMessage(content=event.text))
        self.update_history(self.session)
        self._reset_streaming_state()
    
    async def handle_assistant_message(self, event: AssistantMessageEvent) -> None:
        self.log(event.text)

        self.current_response = event.text
        self._upsert_assistant_message(content=self.current_response)
        self.update_history(self.session)
        self._reset_streaming_state()
    
    async def handle_thought_message(self, event: ThoughtMessageEvent) -> None:
        self.log(event.text)

        self.current_reasoning = event.text
        self._upsert_assistant_message(reasoning=self.current_reasoning)
        self.update_history(self.session)
        self.current_response = ""
    
    async def handle_status(self, event: StatusEvent) -> None:
        self.log(event.state)
        await self.set_status(self._format_status(event.state))
    
    async def handle_error(self, event: ErrorEvent) -> None:
        self.log(event.message)
    
    async def handle_interrupted(self, event: InterruptedEvent) -> None:
        await self.trigger_interrupted_status()
    
    def update_history(self, history_list: Session) -> None:
        session = self.query_one("#message-history", MessageHistory)
        session.update_history(history_list)

        scroll = self.query_one("#main-scroll", ScrollableContainer)
        scroll.scroll_end(animate=False)

if __name__ == "__main__":
    app = TUI()
    app.run()