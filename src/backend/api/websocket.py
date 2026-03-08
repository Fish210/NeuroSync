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

from api.models import ConversationTurnPayload, WebSocketEnvelope
from session.store import session_store
from agents.lock import speaker_running
from agents.speaker import generate_response
from voice.tts import synthesize_and_stream
from voice.vad import VoiceActivityDetector

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

# Per-session VAD detector instances
_vad_detectors: dict[str, "VoiceActivityDetector"] = {}

# Per-session active TTS asyncio tasks (cancellable for barge-in)
_active_tts_tasks: dict[str, asyncio.Task] = {}


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

    # Initialize per-session VAD
    if session_id not in _vad_detectors:
        _vad_detectors[session_id] = VoiceActivityDetector()

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
        # Cancel any active TTS for this session
        task = _active_tts_tasks.pop(session_id, None)
        if task and not task.done():
            task.cancel()
        _vad_detectors.pop(session_id, None)
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
    Calls speaker agent → broadcasts CONVERSATION_TURN → streams TTS audio.
    """
    text = payload.get("text", "")
    if not text:
        return

    logger.info("Student speech [%s]: %s", session_id, text[:80])

    session = session_store.get(session_id)
    if not session:
        logger.warning("Student speech for unknown session: %s", session_id)
        return

    # Store student turn
    session_store.add_turn(session_id, "student", text)

    # Generate tutor response under speaker lock
    try:
        async with speaker_running(session_id):
            result = await generate_response(
                student_text=text,
                current_state=session.current_state,
                current_strategy=session.current_strategy.strategy,
                topic=session.topic,
                conversation=session.conversation,
            )
    except Exception as exc:
        logger.error("Speaker generation failed for session %s: %s", session_id, exc, exc_info=True)
        from api.models import SessionEventPayload
        await manager.broadcast(
            session_id,
            WebSocketEnvelope.session_event(
                SessionEventPayload(type="error", data={"source": "speaker", "message": str(exc)})
            ),
        )
        return

    # Store tutor turn
    session_store.add_turn(
        session_id,
        "tutor",
        result["response"],
        strategy=result["strategy"],
        tone=result["tone"],
    )

    # Broadcast CONVERSATION_TURN to frontend
    envelope = WebSocketEnvelope.conversation_turn(
        ConversationTurnPayload(
            speaker="tutor",
            strategy=result["strategy"],
            tone=result["tone"],
            text=result["response"],
            triggered_by_state=session.current_state,
        )
    )
    await manager.broadcast(session_id, envelope)

    # Cancel any prior TTS and start new one
    prior_task = _active_tts_tasks.pop(session_id, None)
    if prior_task and not prior_task.done():
        prior_task.cancel()

    tts_task = asyncio.create_task(
        synthesize_and_stream(result["response"], session_id, manager)
    )
    _active_tts_tasks[session_id] = tts_task


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
    Voice activity detection signal from browser (every 100ms).
    If barge-in detected while TTS is active, cancel TTS and send INTERRUPT.
    """
    level = float(payload.get("level", 0.0))

    vad = _vad_detectors.get(session_id)
    if vad is None:
        return

    barge_in = vad.update(level)

    if barge_in:
        # Cancel active TTS
        task = _active_tts_tasks.pop(session_id, None)
        if task and not task.done():
            task.cancel()
            logger.info("VAD barge-in: cancelled TTS for session %s", session_id)

        # Send INTERRUPT to frontend so it stops audio playback
        await manager.broadcast(session_id, WebSocketEnvelope.interrupt())
