from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket

from gateway.server_module import Server


@asynccontextmanager
async def lifespan(app: FastAPI):
    server = await Server.create()
    app.state.server = server

    yield

app = FastAPI(lifespan=lifespan)

@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Raga is online"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    server: Server = websocket.app.state.server

    await websocket.accept()

    disconnect_event = await server.connect(websocket)
    await disconnect_event