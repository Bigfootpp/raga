import asyncio
import json
import traceback
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect, WebSocketException
from fastapi.websockets import WebSocketState
from pydantic import ValidationError

from shared.frames import Action, ActionUnion, ErrorEvent, ErrorMessage, to_action
from shared.frames_rpc import (
    ErrorMessageRPC,
    ErrorRes,
    FrameType,
    RequestUnion,
    ResponseUnion,
    to_request,
)
from utils import async_utils


class TransactionClosedError(Exception):
    pass

class TransactionMismatchError(Exception):
    pass

class Transaction:
    def __init__(self, ws: WebSocket, request: RequestUnion) -> None:
        self.ws = ws
        self.connected = True
        self.open = True
        self.request = request
        self.stream = request.stream
        self.lock = asyncio.Lock()

    def get_request(self):
        return self.request

    async def send_response(self, response: ResponseUnion, disconnect_ok: bool = False):
        async with self.lock:
            if not self.open:
                raise TransactionClosedError(f"Transaction {self.request.id} is already closed")
            if response.id != self.request.id:
                raise TransactionMismatchError(f"Response id {response.id} does not match request id {self.request.id}")

            try:
                await self.ws.send_json(response.to_dict())
            except (WebSocketDisconnect, WebSocketException):
                if not disconnect_ok:
                    raise
            self.open = response.has_more and self.request.stream

class ConnectionManager:
    def __init__(self):
        self.connections: set[WebSocket] = set()
        self.events: dict[WebSocket, asyncio.Event] = {}
        self.tasks: dict[WebSocket, asyncio.Task] = {}
        self.action_queue: asyncio.Queue[tuple[WebSocket, ActionUnion]] = asyncio.Queue()
        self.handlers: dict[type[RequestUnion], Callable[[Any], AsyncGenerator[ResponseUnion, None]]] = {}

    def _resolve_handler(self, request: RequestUnion) -> Callable[[Any], AsyncGenerator[ResponseUnion, None]] | None:
        for request_type, handler in self.handlers.items():
            if isinstance(request, request_type):
                return handler
        return None

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

    def on[TRequest: RequestUnion](
        self,
        request: type[TRequest],
        func: Callable[[TRequest], AsyncGenerator[ResponseUnion, None]],
    ):
        self.handlers[request] = func

    async def recv_action(self) -> tuple[WebSocket, Action]:
        return await self.action_queue.get()

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

    @async_utils.background_task
    async def _handle_request(self, transaction: Transaction):
        request = transaction.get_request()
        handler = self._resolve_handler(request)
        if not handler:
            return
        gen = handler(request)

        async for response in gen:
            try:
                await transaction.send_response(response, disconnect_ok=True)
            except (TransactionClosedError, TransactionMismatchError) as e:
                try:
                    await gen.athrow(e)
                except e.__class__:
                    pass
                finally:
                    await gen.aclose()
            except Exception:
                try:
                    await transaction.send_response(
                        ErrorRes(id=request.id, message=ErrorMessageRPC.INTERNAL_ERROR),
                        disconnect_ok=True
                    )
                except (TransactionClosedError, TransactionMismatchError):
                    pass

    async def _listen_loop(self, ws: WebSocket):
        while True:
            try:
                frame_json: dict = json.loads(await ws.receive_text())
                if frame_json.get("type", "") == FrameType.REQUEST:
                    request: RequestUnion = to_request(frame_json)
                    transaction = Transaction(ws=ws, request=request)
                    self._handle_request(transaction=transaction)
                else:
                    action: Action = to_action(frame_json)
                    await self.action_queue.put((ws, action))
            except Exception as e:
                need_break = await self.handle_error(e=e, ws=ws)
                if need_break:
                    break
        self.tasks.pop(ws)
        self.connections.discard(ws)
        if ws.state == WebSocketState.CONNECTED:
            try:
                await ws.close()
            except (WebSocketDisconnect, WebSocketException):
                pass
        event = self.events.get(ws)
        if event is not None:
            event.set()