"""
REST API routes.

Endpoints:
    GET  /health          — smoke check
    POST /start-session   — create session, return lesson plan stub
    POST /stop-session    — end session, return summary
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException

from api.models import (
    LessonBlock,
    LessonPlan,
    SessionSummary,
    StartSessionRequest,
    StartSessionResponse,
    StopSessionResponse,
)
from session.events import event_log
from session.store import session_store
from session.tracker import TopicStateTracker

logger = logging.getLogger(__name__)

router = APIRouter()

# Path to stub lesson plans (used in Phase 1 before Featherless planner)
LESSON_STUB_PATH = Path(__file__).parent.parent.parent.parent / "config" / "backend" / "lesson_stub.json"

# In-memory state log per session: list of (timestamp, state)
_session_state_logs: dict[str, list[tuple[float, str]]] = {}
_session_trackers: dict[str, TopicStateTracker] = {}


def _load_lesson_stub(topic: str) -> dict:
    """Load lesson plan from config stub file."""
    try:
        with open(LESSON_STUB_PATH) as f:
            stubs = json.load(f)
        # Try exact match, then first available
        if topic in stubs:
            return stubs[topic]
        key = next(iter(stubs))
        logger.warning("Topic '%s' not in stub, using '%s'", topic, key)
        return stubs[key]
    except FileNotFoundError:
        logger.warning("lesson_stub.json not found, using minimal fallback")
        return {
            "topic": topic,
            "blocks": [
                {"id": "block-1", "title": f"Introduction to {topic}", "difficulty": 1},
                {"id": "block-2", "title": f"Core concepts of {topic}", "difficulty": 2},
                {"id": "block-3", "title": f"Practice: {topic}", "difficulty": 3},
            ],
            "current_block": "block-1",
        }


@router.get("/health")
async def health() -> dict:
    """Smoke check — returns OK and active session count."""
    return {
        "status": "ok",
        "sessions": len(session_store.list_ids()),
        "timestamp": time.time(),
    }


@router.post("/start-session", response_model=StartSessionResponse)
async def start_session(request: StartSessionRequest) -> StartSessionResponse:
    """
    Create a new tutoring session.

    Phase 1: returns static lesson plan stub from config/backend/lesson_stub.json
    Phase 2: will call Featherless planner to generate plan dynamically
    """
    lesson_data = _load_lesson_stub(request.topic)

    lesson_plan = LessonPlan(
        topic=lesson_data["topic"],
        blocks=[LessonBlock(**b) for b in lesson_data["blocks"]],
        current_block=lesson_data["current_block"],
    )

    session = session_store.create(
        topic=request.topic,
        lesson_plan=lesson_plan.model_dump(),
    )

    # Initialize tracker and state log
    _session_trackers[session.session_id] = TopicStateTracker(lesson_plan.model_dump())
    _session_state_logs[session.session_id] = [(time.time(), "DISENGAGED")]

    event_log.record(
        "session_started",
        session.session_id,
        {"topic": request.topic},
    )

    logger.info("Session started: %s topic=%s", session.session_id, request.topic)

    return StartSessionResponse(
        session_id=session.session_id,
        lesson_plan=lesson_plan,
    )


@router.post("/stop-session", response_model=StopSessionResponse)
async def stop_session(body: dict) -> StopSessionResponse:
    """
    End a tutoring session and return the post-session summary.
    """
    session_id = body.get("session_id", "")
    session = session_store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    tracker = _session_trackers.get(session_id)
    state_log = _session_state_logs.get(session_id, [])

    summary_data: dict = {"duration_seconds": 0, "state_breakdown": {}, "topics": []}
    if tracker and state_log:
        summary_data = tracker.compute_summary(state_log)

    adaptation_events = event_log.get_state_transitions(session_id)
    summary_data["adaptation_events"] = adaptation_events

    summary = SessionSummary(**summary_data)

    event_log.record("session_stopped", session_id)
    session_store.delete(session_id)
    _session_trackers.pop(session_id, None)
    _session_state_logs.pop(session_id, None)

    return StopSessionResponse(summary=summary)


def record_state_for_session(session_id: str, state: str) -> None:
    """Called by WebSocket hub when a new state update arrives."""
    log = _session_state_logs.get(session_id)
    if log is not None:
        log.append((time.time(), state))
    tracker = _session_trackers.get(session_id)
    if tracker:
        tracker.record(state)
