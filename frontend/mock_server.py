import asyncio
import json
import time
from fastapi import FastAPI, WebSocket
import uvicorn

app = FastAPI()

MESSAGES = [
    {
        "event_type": "SESSION_EVENT",
        "payload": {
            "type": "session_started",
            "data": {}
        },
        "timestamp": int(time.time())
    },
    {
        "event_type": "STATE_UPDATE",
        "payload": {
            "state": "FOCUSED",
            "confidence": 0.82,
            "bands": {
                "alpha": 0.35,
                "beta": 0.62,
                "theta": 0.18,
                "gamma": 0.41,
                "delta": 0.12
            }
        },
        "timestamp": int(time.time())
    },
    {
        "event_type": "CONVERSATION_TURN",
        "payload": {
            "speaker": "tutor",
            "strategy": "increase_difficulty",
            "tone": "challenging",
            "text": "You seem focused, so let's try a harder derivative example.",
            "triggered_by_state": "FOCUSED"
        },
        "timestamp": int(time.time())
    },
    {
        "event_type": "STATE_UPDATE",
        "payload": {
            "state": "OVERLOADED",
            "confidence": 0.77,
            "bands": {
                "alpha": 0.22,
                "beta": 0.49,
                "theta": 0.44,
                "gamma": 0.31,
                "delta": 0.15
            }
        },
        "timestamp": int(time.time())
    },
    {
        "event_type": "CONVERSATION_TURN",
        "payload": {
            "speaker": "tutor",
            "strategy": "step_by_step",
            "tone": "slow",
            "text": "Let's slow down and break this into smaller steps.",
            "triggered_by_state": "OVERLOADED"
        },
        "timestamp": int(time.time())
    },
    {
        "event_type": "STATE_UPDATE",
        "payload": {
            "state": "DISENGAGED",
            "confidence": 0.73,
            "bands": {
                "alpha": 0.51,
                "beta": 0.19,
                "theta": 0.48,
                "gamma": 0.14,
                "delta": 0.21
            }
        },
        "timestamp": int(time.time())
    },
    {
        "event_type": "CONVERSATION_TURN",
        "payload": {
            "speaker": "tutor",
            "strategy": "re_engage",
            "tone": "encouraging",
            "text": "Let's reset with a quick question. What does a derivative represent?",
            "triggered_by_state": "DISENGAGED"
        },
        "timestamp": int(time.time())
    }
]

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    i = 0
    try:
        while True:
            msg = dict(MESSAGES[i % len(MESSAGES)])
            msg["timestamp"] = int(time.time())
            await ws.send_text(json.dumps(msg))
            i += 1
            await asyncio.sleep(2)
    except Exception:
        try:
            await ws.close()
        except Exception:
            pass

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)