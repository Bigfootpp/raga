import asyncio
import json
from typing import Optional

import websockets
from websockets.asyncio.client import ClientConnection, connect

from utils.frames import (
    AssistantMessageEvent,
    Event,
    InterruptedEvent,
    SendMessageAction,
    StatusEvent,
    ResponseChunkEvent,
    ThoughtChunkEvent,
    ErrorEvent,
    ThoughtMessageEvent,
    UserMessageEvent,
    to_event
)

class Client:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.uri = "ws://127.0.0.1:8000/ws"
        self.reconnect_delay = 1
        self.connected: bool = False
        
        self.websocket: Optional[ClientConnection] = None
        self._listen_task: Optional[asyncio.Task] = None
        self._running_connection: bool = False

    async def connect(self):
        if self._running_connection:
            return
            
        self._running_connection = True
        self._listen_task = asyncio.create_task(self._reconnect_loop())

    async def _reconnect_loop(self):
        while self._running_connection:
            try:
                self.websocket = await connect(self.uri)
                self.connected = True
                await self.handle_connect()
                
                await self._listen_loop()
                
            except asyncio.CancelledError:
                break
            except Exception:
                pass
            finally:
                if self.websocket:
                    self.connected = False
                    self.websocket = None
                    await self.handle_disconnect()

            if self._running_connection:
                await asyncio.sleep(self.reconnect_delay)

    async def _listen_loop(self):
        if not self.websocket:
            return
            
        async for message in self.websocket:
            try:
                event_json: dict = json.loads(message)
                event = to_event(event_json)
                if event:
                    await self._dispatch(event)
            except Exception:
                pass

    async def _dispatch(self, event: Event):
        match event:
            case ResponseChunkEvent():
                await self.handle_response(event)
            case ThoughtChunkEvent():
                await self.handle_thought(event)
            case StatusEvent():
                await self.handle_status(event)
            case ErrorEvent():
                await self.handle_error(event)
            case InterruptedEvent():
                await self.handle_interrupted(event)
            case UserMessageEvent():
                await self.handle_user_message(event)
            case AssistantMessageEvent():
                await self.handle_assistant_message(event)
            case ThoughtMessageEvent():
                await self.handle_thought_message(event)

    async def process_input(self, msg: str):
        if self.websocket and self.websocket.state == websockets.State.OPEN:
            action_json = json.dumps(SendMessageAction(text=msg).to_dict())
            await self.websocket.send(action_json)
        else:
            raise ConnectionError("Unable to send the message, the client is not connected.")

    async def handle_connect(self) -> None: ...
    async def handle_disconnect(self) -> None: ...
    async def handle_user_message(self, event: UserMessageEvent) -> None: ...
    async def handle_assistant_message(self, event: AssistantMessageEvent) -> None: ...
    async def handle_thought_message(self, event: ThoughtMessageEvent) -> None: ...
    async def handle_response(self, event: ResponseChunkEvent) -> None: ...
    async def handle_thought(self, event: ThoughtChunkEvent) -> None: ...
    async def handle_status(self, event: StatusEvent) -> None: ...
    async def handle_error(self, event: ErrorEvent) -> None: ...
    async def handle_interrupted(self, event: InterruptedEvent) -> None: ...

    async def close(self):
        self._running_connection = False

        if self.websocket:
            try:
                if self.websocket.state == websockets.State.OPEN:
                    await self.websocket.close()
            except Exception:
                pass
            self.websocket = None

        if self._listen_task:
            if not self._listen_task.done():
                self._listen_task.cancel()
                try:
                    await self._listen_task
                except asyncio.CancelledError:
                    pass
            self._listen_task = None