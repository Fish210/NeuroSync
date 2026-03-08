"""
NeuroSync Mock Server — Day 1 Frontend Development Tool

Emits a scripted sequence of WebSocket events that matches the real backend
contract exactly. Frontend team can build and wire all components against this.

Run: uvicorn examples.mock_server:app --port 8001 --app-dir .
Or:  cd examples && uvicorn mock_server:app --port 8001

Frontend WS URL: ws://localhost:8001/ws/session/demo
"""
from __future__ import annotations

import asyncio
import json
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="NeuroSync Mock Server", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Mock REST endpoints (match real backend contract exactly)
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok", "sessions": 1, "timestamp": time.time()}


@app.post("/start-session")
async def start_session(body: dict):
    topic = body.get("topic", "derivatives")
    return {
        "session_id": "demo",
        "lesson_plan": {
            "topic": topic,
            "blocks": [
                {"id": "block-1", "title": "What is a derivative?", "difficulty": 1},
                {"id": "block-2", "title": "The limit definition", "difficulty": 2},
                {"id": "block-3", "title": "Power rule basics", "difficulty": 2},
                {"id": "block-4", "title": "Chain rule introduction", "difficulty": 3},
                {"id": "block-5", "title": "Practice problem", "difficulty": 3},
            ],
            "current_block": "block-1",
        },
    }


@app.post("/stop-session")
async def stop_session(body: dict):
    return {
        "summary": {
            "duration_seconds": 240,
            "state_breakdown": {"FOCUSED": 120, "OVERLOADED": 80, "DISENGAGED": 40},
            "topics": [
                {
                    "title": "What is a derivative?",
                    "duration_seconds": 90,
                    "dominant_state": "FOCUSED",
                    "comprehension": "strong",
                },
                {
                    "title": "The limit definition",
                    "duration_seconds": 150,
                    "dominant_state": "OVERLOADED",
                    "comprehension": "needs_review",
                },
            ],
            "adaptation_events": [
                {
                    "timestamp": time.time() - 120,
                    "from_state": "FOCUSED",
                    "to_state": "OVERLOADED",
                    "strategy_applied": "step_by_step",
                },
                {
                    "timestamp": time.time() - 60,
                    "from_state": "OVERLOADED",
                    "to_state": "DISENGAGED",
                    "strategy_applied": "re_engage",
                },
            ],
        }
    }


# ---------------------------------------------------------------------------
# Scripted WebSocket sequence
# ---------------------------------------------------------------------------

def _envelope(event_type: str, payload: dict) -> str:
    return json.dumps({
        "event_type": event_type,
        "payload": payload,
        "timestamp": time.time(),
    })


def _state_update(state: str, alpha: float, beta: float, theta: float, gamma: float, delta: float, confidence: float = 0.8) -> str:
    return _envelope("STATE_UPDATE", {
        "state": state,
        "confidence": confidence,
        "bands": {
            "alpha": alpha,
            "beta": beta,
            "theta": theta,
            "gamma": gamma,
            "delta": delta,
            "timestamp": time.time(),
        },
    })


def _session_event(type_: str, data: dict | None = None) -> str:
    return _envelope("SESSION_EVENT", {"type": type_, "data": data or {}})


def _conversation_turn(text: str, strategy: str, tone: str, triggered_by: str | None = None) -> str:
    return _envelope("CONVERSATION_TURN", {
        "speaker": "tutor",
        "strategy": strategy,
        "tone": tone,
        "text": text,
        "triggered_by_state": triggered_by,
    })


def _whiteboard_delta(type_: str, content: str, x: float = 50, y: float = 100) -> str:
    import uuid
    return _envelope("WHITEBOARD_DELTA", {
        "author": "tutor",
        "type": type_,
        "content": content,
        "position": {"x": x, "y": y},
        "id": str(uuid.uuid4()),
    })


# Scripted demo sequence: list of (delay_seconds, message_fn)
DEMO_SCRIPT = [
    # t=0: session start
    (0.5, lambda: _session_event("session_started", {"session_id": "demo"})),
    (1.0, lambda: _session_event("eeg_connected")),
    # t=2: baseline FOCUSED state
    (2.0, lambda: _state_update("FOCUSED", 0.35, 0.42, 0.18, 0.28, 0.22, 0.78)),
    # t=4: tutor introduces topic
    (4.0, lambda: _conversation_turn(
        "Welcome! Today we're exploring derivatives. A derivative tells us the rate of change of a function. Let's start with an intuitive picture.",
        "continue", "neutral",
    )),
    (4.5, lambda: _whiteboard_delta("text", "Derivative = rate of change", 60, 80)),
    # t=7: still focused
    (7.0, lambda: _state_update("FOCUSED", 0.38, 0.45, 0.17, 0.30, 0.20, 0.82)),
    # t=9: tutor advances
    (9.0, lambda: _conversation_turn(
        "Mathematically, the derivative is defined as a limit. This is where it gets precise.",
        "increase_difficulty", "encouraging",
    )),
    (9.5, lambda: _whiteboard_delta("katex", r"f'(x) = \lim_{h \to 0} \frac{f(x+h) - f(x)}{h}", 40, 160)),
    # t=12: cognitive load rising — OVERLOADED
    (12.0, lambda: _state_update("OVERLOADED", 0.22, 0.68, 0.15, 0.55, 0.18, 0.75)),
    # t=13: state transition + adaptation
    (13.0, lambda: _session_event("contact_quality", {"TP9": 1.1, "AF7": 1.0, "AF8": 1.2, "TP10": 1.1, "overall": "good"})),
    (14.0, lambda: _conversation_turn(
        "That seemed like a lot at once. Let me slow down. Step one: forget the formula for now.",
        "step_by_step", "slow", "OVERLOADED",
    )),
    (14.5, lambda: _whiteboard_delta("text", "Step 1: What does 'rate of change' mean?", 60, 250)),
    # t=17: slight recovery
    (17.0, lambda: _state_update("OVERLOADED", 0.28, 0.61, 0.19, 0.48, 0.21, 0.70)),
    # t=20: student question
    (20.0, lambda: _envelope("CONVERSATION_TURN", {
        "speaker": "student",
        "strategy": "",
        "tone": "",
        "text": "Is it like the slope of a line but for curves?",
        "triggered_by_state": None,
    })),
    (21.0, lambda: _conversation_turn(
        "Exactly! That's a perfect intuition. At any point on a curve, the derivative is the slope of the tangent line.",
        "continue", "encouraging",
    )),
    (21.5, lambda: _whiteboard_delta("katex", r"\text{slope} = \frac{\Delta y}{\Delta x} \to \frac{dy}{dx}", 40, 300)),
    # t=25: disengaged
    (25.0, lambda: _state_update("DISENGAGED", 0.48, 0.25, 0.38, 0.20, 0.35, 0.72)),
    (27.0, lambda: _conversation_turn(
        "Let me check in — are you still with me? Quick question: if f(x) = x², what do you think the derivative might be?",
        "re_engage", "curious", "DISENGAGED",
    )),
    # t=30: back to focused
    (30.0, lambda: _state_update("FOCUSED", 0.40, 0.44, 0.16, 0.29, 0.21, 0.85)),
    (31.0, lambda: _conversation_turn(
        "Great response! The derivative of x² is 2x. This is the power rule — one of the most useful tools in calculus.",
        "increase_difficulty", "encouraging",
    )),
    (31.5, lambda: _whiteboard_delta("katex", r"\frac{d}{dx}[x^n] = nx^{n-1}", 40, 380)),
    # t=35: loop back to cycle
    (35.0, lambda: _state_update("FOCUSED", 0.41, 0.46, 0.15, 0.31, 0.20, 0.88)),
    (38.0, lambda: _state_update("OVERLOADED", 0.20, 0.70, 0.14, 0.58, 0.19, 0.77)),
    (40.0, lambda: _conversation_turn(
        "Let's pause here. Take a breath. I'll simplify what we just covered.",
        "simplify", "slow", "OVERLOADED",
    )),
]


async def run_demo_script(websocket: WebSocket) -> None:
    """Play through the scripted sequence, looping after completion."""
    start = time.time()
    sent_indices: set[int] = set()

    while True:
        elapsed = time.time() - start

        for i, (delay, msg_fn) in enumerate(DEMO_SCRIPT):
            if i not in sent_indices and elapsed >= delay:
                try:
                    await websocket.send_text(msg_fn())
                    sent_indices.add(i)
                except Exception:
                    return

        # After full script, reset and loop
        if len(sent_indices) >= len(DEMO_SCRIPT):
            start = time.time()
            sent_indices.clear()

        await asyncio.sleep(0.25)


@app.websocket("/ws/session/{session_id}")
async def ws_endpoint(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()

    # Run scripted sequence and also accept client messages
    script_task = asyncio.create_task(run_demo_script(websocket))

    try:
        while True:
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
                # Echo student speech back as tutor response for UI testing
                try:
                    data = json.loads(raw)
                    if data.get("event_type") == "STUDENT_SPEECH":
                        text = data.get("payload", {}).get("text", "")
                        response = _conversation_turn(
                            f"[Mock] You said: '{text}' — great question!",
                            "continue", "neutral",
                        )
                        await websocket.send_text(response)
                except Exception:
                    pass
            except asyncio.TimeoutError:
                pass  # no message from client — continue script
    except WebSocketDisconnect:
        pass
    finally:
        script_task.cancel()
