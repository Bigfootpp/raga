import asyncio
import traceback
from typing import Awaitable

from fastapi import WebSocket, WebSocketDisconnect, WebSocketException
from pydantic import ValidationError
from shared.frames import Action, ErrorEvent, ErrorMessage, to_action

# TODO: Support RPC method request with Transaction Class
class Transaction:
    pass

class ConnectionManager:
    def __init__(self):
        self.connections: set[WebSocket] = set()
        self.events: dict[WebSocket, asyncio.Event] = {}
        self.tasks: dict[WebSocket, asyncio.Task] = {}
        self.queue: asyncio.Queue[tuple[WebSocket, Action]] = asyncio.Queue()
    
    async def connect(self, ws: WebSocket) -> Awaitable[None]:
        self.connections.add(ws)
        task = asyncio.create_task(self._listen_loop(ws=ws))
        self.tasks[ws] = task
        self.events[ws] = asyncio.Event()
        return self.disconnected(ws=ws)

    async def disconnected(self, ws: WebSocket):
        event = self.events.get(ws)
        if event is None:
            return
        
        await event.wait()
        self.events.pop(ws)
    
    async def recv_action(self) -> tuple[WebSocket, Action]:
        return await self.queue.get()
    
    async def handle_error(self, e: Exception, ws: WebSocket) -> bool:
        print(f"Error: ({e.__class__.__name__})")
        unexpected = False
        need_break = False
        match e:
            case ValidationError():
                try:
                    await ws.send_json(ErrorEvent(message=ErrorMessage.INVALID_FORMAT, details=e.errors()).to_dict())
                except Exception:
                    need_break = True
            case WebSocketException() | WebSocketDisconnect():
                need_break = True
            case asyncio.CancelledError():
                need_break = True
            case Exception():
                unexpected = True
                try:
                    await ws.send_json(ErrorEvent(message=ErrorMessage.INTERNAL_ERROR).to_dict())
                except Exception:
                    need_break = True
        
        if unexpected:
            print(traceback.print_exc())
        return need_break

    async def _listen_loop(self, ws: WebSocket):
        while True:
            try:
                action: Action = to_action(await ws.receive_text())

                await self.queue.put((ws, action))
            except Exception as e:
                need_break = await self.handle_error(e=e, ws=ws)
                if need_break:
                    break
        self.tasks.pop(ws)
        self.connections.discard(ws)
        try:
            await ws.close()
        except Exception:
            pass
        event = self.events.get(ws)
        if event is not None:
            event.set()