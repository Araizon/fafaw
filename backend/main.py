import os, asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from agents import AGENTS, agent_status
from orchestrator import process
import memory

app = FastAPI(title="Fafaw API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Active connections ────────────────────────────────────────────────────────

active_ws: set[WebSocket] = set()
is_processing = False  # prevent overlapping requests


async def broadcast(data: dict):
    dead = set()
    for ws in active_ws:
        try:
            await ws.send_json(data)
        except Exception:
            dead.add(ws)
    active_ws.difference_update(dead)


# ─── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    global is_processing
    await ws.accept()
    active_ws.add(ws)

    # Send initial state
    await ws.send_json({
        "type":   "init",
        "agents": [
            {"name": name, "emoji": cfg["emoji"], "color": cfg["color"], "offline": False}
            for name, cfg in AGENTS.items()
        ],
    })

    # Send chat history
    history = await memory.get_history(60)
    if history:
        await ws.send_json({"type": "history", "messages": history})

    try:
        while True:
            data = await ws.receive_json()

            if data.get("type") == "ping":
                await ws.send_json({"type": "pong"})
                continue

            if data.get("type") != "message":
                continue

            user_msg = data.get("content", "").strip()
            if not user_msg:
                continue

            if is_processing:
                await ws.send_json({"type": "system",
                                    "content": "⏳ এক মিনিট, আগের reply এখনো আসছে..."})
                continue

            is_processing = True

            # Save user message
            await memory.save_message("You", user_msg, "text")

            # Get context for AI
            ctx = await memory.get_context(20)

            async def save_and_broadcast(msg: dict):
                await broadcast(msg)
                if msg["type"] == "message":
                    await memory.save_message(
                        msg["agent"], msg["content"], msg["msg_type"]
                    )

            try:
                await process(user_msg, save_and_broadcast, ctx)
            finally:
                is_processing = False

    except WebSocketDisconnect:
        active_ws.discard(ws)
    except Exception:
        active_ws.discard(ws)


# ─── REST endpoints ────────────────────────────────────────────────────────────

@app.get("/history")
async def get_history():
    return await memory.get_history(100)


@app.get("/status")
async def get_status():
    return {name: {"offline": off, **{k: v for k, v in AGENTS[name].items()
                                       if k not in ("personality", "api", "model", "delay")}}
            for name, off in agent_status.items()}


@app.post("/reset-agent/{name}")
async def reset_agent(name: str):
    if name in agent_status:
        agent_status[name] = False
        await broadcast({"type": "agent_status", "agents": {name: False}})
        return {"ok": True}
    return {"ok": False}


@app.get("/")
async def root():
    return {"status": "Fafaw backend running 🚀"}
