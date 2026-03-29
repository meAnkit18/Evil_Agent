"""
EvilAgent — WebSocket API server.

Connects the MainAgent to the Electron/web UI via WebSocket.
Incoming messages are routed through the agent pipeline and results streamed back.
"""

import os
import sys
import json

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from websocket.manager import manager

# Ensure src/ is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

app = FastAPI(title="EvilAgent", version="2.0")

# Lazy-initialize agent (created on first connection)
_agent = None


def get_agent():
    """Lazy agent initialization."""
    global _agent
    if _agent is None:
        from agents.main_agent.agent import MainAgent
        _agent = MainAgent()
    return _agent


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)

    try:
        while True:
            data = await websocket.receive_text()
            print(f"📥 Received: {data[:100]}")

            try:
                payload = json.loads(data)
                user_input = payload.get("message", payload.get("data", data))
            except json.JSONDecodeError:
                user_input = data

            # Send "thinking" status
            await manager.send_message(json.dumps({
                "type": "status",
                "data": "thinking",
            }))

            # Route through the agent
            agent = get_agent()
            response = agent.handle(user_input)

            # Send result
            await manager.send_message(json.dumps({
                "type": "chat",
                "data": response.message,
            }))

            # Send task details if available
            if response.task_result:
                await manager.send_message(json.dumps({
                    "type": "task_result",
                    "data": response.task_result.to_dict(),
                }))

            # Send state snapshot
            if response.state_snapshot:
                await manager.send_message(json.dumps({
                    "type": "state",
                    "data": response.state_snapshot,
                }))

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print("Client disconnected")