"""
In-memory session store.

Holds all session state in a single dict keyed by session_id.
No database. Session state lives only for the duration of the process.

SPEAKER_RUNNING lock: prevents the planner agent from mutating strategy
while the speaker agent is generating a response.

Race condition prevention:
    - current_strategy: read-only while SPEAKER_RUNNING is held
    - pending_strategy: planner writes here when speaker is active
    - Speaker reads current_strategy at start of each turn
    - After speaker completes, current_strategy is updated from pending_strategy
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SessionStrategy:
    strategy: str = "continue"
    tone: str = "neutral"
    updated_at: float = field(default_factory=time.time)


@dataclass
class SessionData:
    session_id: str
    topic: str
    lesson_plan: dict[str, Any]
    created_at: float = field(default_factory=time.time)

    # Current cognitive state (set by EEG pipeline)
    current_state: str = "DISENGAGED"
    state_updated_at: float = field(default_factory=time.time)

    # Tutor strategy
    current_strategy: SessionStrategy = field(default_factory=SessionStrategy)
    pending_strategy: SessionStrategy | None = None  # set by planner during speaker lock

    # Conversation history
    conversation: list[dict[str, Any]] = field(default_factory=list)

    # SPEAKER_RUNNING lock — asyncio lock, prevents planner mutation mid-response
    speaker_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    # Active WebSocket connections for this session (set by websocket hub)
    ws_connections: set = field(default_factory=set)


class SessionStore:
    """
    Global in-memory session store.

    Thread-safety note: FastAPI runs in a single-threaded asyncio event loop.
    All access to this store must happen from coroutines (not threads).
    The EEG ingestion thread communicates via asyncio.Queue.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, SessionData] = {}

    def create(self, topic: str, lesson_plan: dict[str, Any]) -> SessionData:
        """Create a new session and return it."""
        session_id = str(uuid.uuid4())[:8]  # short ID for readability
        session = SessionData(
            session_id=session_id,
            topic=topic,
            lesson_plan=lesson_plan,
        )
        self._sessions[session_id] = session
        logger.info("Session created: %s (topic=%s)", session_id, topic)
        return session

    def get(self, session_id: str) -> SessionData | None:
        return self._sessions.get(session_id)

    def require(self, session_id: str) -> SessionData:
        """Get session or raise KeyError."""
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Session not found: {session_id}")
        return session

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        logger.info("Session deleted: %s", session_id)

    def list_ids(self) -> list[str]:
        return list(self._sessions.keys())

    async def update_state(self, session_id: str, state: str) -> bool:
        """Update cognitive state. Returns True if state changed."""
        session = self._sessions.get(session_id)
        if not session:
            return False

        changed = session.current_state != state
        session.current_state = state
        session.state_updated_at = time.time()

        if changed:
            logger.info("Session %s state: %s", session_id, state)
        return changed

    async def apply_pending_strategy(self, session_id: str) -> bool:
        """
        If planner set a pending_strategy while speaker was active,
        apply it now. Called by speaker agent after completing a turn.
        Returns True if strategy was updated.
        """
        session = self._sessions.get(session_id)
        if not session or not session.pending_strategy:
            return False

        session.current_strategy = session.pending_strategy
        session.pending_strategy = None
        logger.info(
            "Session %s: applied pending strategy: %s",
            session_id,
            session.current_strategy.strategy,
        )
        return True

    def add_turn(
        self,
        session_id: str,
        speaker: str,
        text: str,
        strategy: str = "",
        tone: str = "",
    ) -> None:
        """Append a conversation turn to the session history."""
        session = self._sessions.get(session_id)
        if session:
            session.conversation.append({
                "speaker": speaker,
                "text": text,
                "strategy": strategy,
                "tone": tone,
                "timestamp": time.time(),
                "cognitive_state": session.current_state,
            })


# Module-level singleton — imported by routes and websocket
session_store = SessionStore()
