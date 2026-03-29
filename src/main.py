from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from websocket.manager import manager
import json

app = FastAPI()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)

    try:
        while True:
            data = await websocket.receive_text()

            print("Received:", data)

            # Echo back (for now)
            await manager.send_message(json.dumps({
                "type": "log",
                "data": f"Received -> {data}"
            }))

            # send chat response
            await manager.send_message(json.dumps({
                "type": "chat",
                "data": f"Server says: {data}"  # reverse for demo
            }))

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print("Client disconnected")