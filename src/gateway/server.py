from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket
from gateway.server_module import Server

@asynccontextmanager
async def lifespan(app: FastAPI):
    connection_manager = await Server.create()
    app.state.connection_manager = connection_manager
    
    yield

app = FastAPI(lifespan=lifespan)

@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Raga is online"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    connection_manager: Server = websocket.app.state.connection_manager
    
    await websocket.accept()
    
    disconnect_event = await connection_manager.connect(websocket)
    await disconnect_event