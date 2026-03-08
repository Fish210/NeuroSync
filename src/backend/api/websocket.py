"""
WebSocket hub.

Manages WebSocket connections keyed by session_id so reconnection
restores the session rather than creating a new one.

Message routing:
    Backend → Frontend: STATE_UPDATE, SESSION_EVENT, CONVERSATION_TURN,
                        AUDIO_CHUNK, INTERRUPT, WHITEBOARD_DELTA
    Frontend → Backend: STUDENT_SPEECH, STUDENT_WHITEBOARD_DELTA, VAD_SIGNAL

WebSocket URL: /ws/session/{session_id}
The session_id in the URL allows the client to reconnect to an existing
session after a network blip without losing session state.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from api.models import WebSocketEnvelope
from session.store import session_store

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Tracks active WebSocket connections per session."""

    def __init__(self) -> None:
        # session_id → set of WebSocket objects
        self._connections: dict[str, set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, session_id: str) -> None:
        await websocket.accept()
        if session_id not in self._connections:
            self._connections[session_id] = set()
        self._connections[session_id].add(websocket)
        logger.info("WS connected: session=%s total=%d", session_id, len(self._connections[session_id]))

    def disconnect(self, websocket: WebSocket, session_id: str) -> None:
        connections = self._connections.get(session_id, set())
        connections.discard(websocket)
        if not connections:
            self._connections.pop(session_id, None)
        logger.info("WS disconnected: session=%s", session_id)

    async def broadcast(self, session_id: str, envelope: WebSocketEnvelope) -> None:
        """Send message to all connections for this session."""
        connections = list(self._connections.get(session_id, set()))
        if not connections:
            return

        message = envelope.encode()
        dead: list[WebSocket] = []

        for ws in connections:
            try:
                await ws.send_text(message)
            except Exception as exc:
                logger.warning("WS send failed: %s", exc)
                dead.append(ws)

        for ws in dead:
            self.disconnect(ws, session_id)

    async def broadcast_raw(self, session_id: str, data: dict[str, Any]) -> None:
        """Broadcast a raw dict (auto-wrapped in WebSocketEnvelope)."""
        envelope = WebSocketEnvelope(**data)
        await self.broadcast(session_id, envelope)

    def get_connection_count(self, session_id: str) -> int:
        return len(self._connections.get(session_id, set()))


# Module-level singleton used by routes and the EEG processing loop
manager = ConnectionManager()


async def handle_websocket(websocket: WebSocket, session_id: str) -> None:
    """
    Main WebSocket handler for a session connection.

    Called by the FastAPI route:
        @app.websocket("/ws/session/{session_id}")
        async def ws_endpoint(ws: WebSocket, session_id: str):
            await handle_websocket(ws, session_id)

    The session must already exist (created via POST /start-session).
    Reconnection to an existing session restores state — the client
    just reconnects to the same /ws/session/{session_id} URL.
    """
    # Validate session exists
    session = session_store.get(session_id)
    if not session:
        await websocket.close(code=4004, reason=f"Session not found: {session_id}")
        return

    await manager.connect(websocket, session_id)

    # Send session restored event on connect/reconnect
    from api.models import SessionEventPayload
    await manager.broadcast(
        session_id,
        WebSocketEnvelope.session_event(
            SessionEventPayload(type="session_started", data={"session_id": session_id})
        ),
    )

    try:
        while True:
            raw = await websocket.receive_text()
            await _handle_client_message(session_id, raw)

    except WebSocketDisconnect:
        manager.disconnect(websocket, session_id)
        logger.info("WS client disconnected: session=%s", session_id)

    except Exception as exc:
        logger.error("WS error for session %s: %s", session_id, exc, exc_info=True)
        manager.disconnect(websocket, session_id)


async def _handle_client_message(session_id: str, raw: str) -> None:
    """Route incoming frontend messages to the appropriate handler."""
    try:
        data = json.loads(raw)
        event_type = data.get("event_type", "")
        payload = data.get("payload", {})
    except json.JSONDecodeError:
        logger.warning("Invalid JSON from client: %s", raw[:100])
        return

    if event_type == "STUDENT_SPEECH":
        await _handle_student_speech(session_id, payload)
    elif event_type == "STUDENT_WHITEBOARD_DELTA":
        await _handle_whiteboard_delta(session_id, payload)
    elif event_type == "VAD_SIGNAL":
        await _handle_vad_signal(session_id, payload)
    else:
        logger.debug("Unhandled WS event_type: %s", event_type)


async def _handle_student_speech(session_id: str, payload: dict) -> None:
    """
    Student speech transcribed by Web Speech API.
    Phase 1: echo back for testing.
    Phase 2: forward to speaker agent.
    """
    text = payload.get("text", "")
    if not text:
        return
    logger.info("Student speech [%s]: %s", session_id, text[:80])
    # Phase 2: forward to speaker agent here
    # For now, add to session conversation history
    session_store.add_turn(session_id, "student", text)


async def _handle_whiteboard_delta(session_id: str, payload: dict) -> None:
    """Broadcast student whiteboard delta to all other connections."""
    from api.models import WhiteboardDeltaPayload
    try:
        delta = WhiteboardDeltaPayload(**payload)
        envelope = WebSocketEnvelope(
            event_type="WHITEBOARD_DELTA",
            payload=delta.model_dump(),
        )
        await manager.broadcast(session_id, envelope)
    except Exception as exc:
        logger.warning("Whiteboard delta error: %s", exc)


async def _handle_vad_signal(session_id: str, payload: dict) -> None:
    """
    Voice activity detection signal from browser.
    If level > 0.6 and tutor is currently speaking, send INTERRUPT.
    Phase 3: wire to active TTS stream cancellation.
    """
    level = float(payload.get("level", 0.0))
    if level > 0.6:
        # Phase 3: cancel active ElevenLabs stream here
        # For now just log
        logger.debug("VAD barge-in signal: level=%.2f session=%s", level, session_id)
