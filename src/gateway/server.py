from fastapi import FastAPI, WebSocket
from agent_core.harness import Harness

app = FastAPI()

@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Raga is online"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    harness = Harness()

    try:
        while True:
            data = await websocket.receive()
            stream = await harness.process_input(data["input"])
            for chunk in stream:
                await websocket.send_json(chunk.to_dict)
            
    except Exception:
        pass