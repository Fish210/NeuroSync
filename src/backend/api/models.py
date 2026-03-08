"""
NeuroSync shared Pydantic models.
All WebSocket envelopes and REST request/response types live here.
Import from: from api.models import ...
"""
from __future__ import annotations

import time
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# EEG / signal types
# ---------------------------------------------------------------------------

class EEGBandPowers(BaseModel):
    alpha: float
    beta: float
    theta: float
    gamma: float
    delta: float
    timestamp: float = Field(default_factory=time.time)


class ContactQuality(BaseModel):
    """Muse HSI channel values. Near 1.0 = good contact, >1.5 = poor."""
    TP9: float
    AF7: float
    AF8: float
    TP10: float
    overall: Literal["good", "poor"]


class CognitiveStateEnum:
    FOCUSED = "FOCUSED"
    OVERLOADED = "OVERLOADED"
    DISENGAGED = "DISENGAGED"


class CognitiveState(BaseModel):
    state: Literal["FOCUSED", "OVERLOADED", "DISENGAGED"]
    confidence: float = Field(ge=0.0, le=1.0)


# ---------------------------------------------------------------------------
# WebSocket payload types
# ---------------------------------------------------------------------------

class StateUpdatePayload(BaseModel):
    state: Literal["FOCUSED", "OVERLOADED", "DISENGAGED"]
    confidence: float
    bands: EEGBandPowers


class SessionEventPayload(BaseModel):
    type: Literal[
        "session_started",
        "session_ended",
        "eeg_connected",
        "eeg_disconnected",
        "eeg_reconnected",
        "lesson_ready",
        "contact_quality",
        "error",
    ]
    data: dict[str, Any] = Field(default_factory=dict)


class ConversationTurnPayload(BaseModel):
    speaker: Literal["tutor", "student"]
    strategy: str
    tone: str
    text: str
    triggered_by_state: str | None = None


class AudioChunkPayload(BaseModel):
    chunk_index: int
    data: str  # base64-encoded audio
    is_final: bool = False


class WhiteboardDeltaPayload(BaseModel):
    author: Literal["tutor", "student"]
    type: Literal["text", "katex", "image", "annotation"]
    content: str
    position: dict[str, float] = Field(default_factory=dict)
    id: str


class InterruptPayload(BaseModel):
    pass


# ---------------------------------------------------------------------------
# WebSocket envelope — all messages use this wrapper
# ---------------------------------------------------------------------------

class WebSocketEnvelope(BaseModel):
    event_type: Literal[
        "STATE_UPDATE",
        "CONVERSATION_TURN",
        "AUDIO_CHUNK",
        "INTERRUPT",
        "WHITEBOARD_DELTA",
        "SESSION_EVENT",
        # frontend → backend
        "STUDENT_SPEECH",
        "STUDENT_WHITEBOARD_DELTA",
        "VAD_SIGNAL",
    ]
    payload: dict[str, Any]
    timestamp: float = Field(default_factory=time.time)

    def encode(self) -> str:
        return self.model_dump_json()

    @classmethod
    def state_update(cls, payload: StateUpdatePayload) -> "WebSocketEnvelope":
        return cls(event_type="STATE_UPDATE", payload=payload.model_dump())

    @classmethod
    def session_event(cls, payload: SessionEventPayload) -> "WebSocketEnvelope":
        return cls(event_type="SESSION_EVENT", payload=payload.model_dump())

    @classmethod
    def conversation_turn(cls, payload: ConversationTurnPayload) -> "WebSocketEnvelope":
        return cls(event_type="CONVERSATION_TURN", payload=payload.model_dump())

    @classmethod
    def interrupt(cls) -> "WebSocketEnvelope":
        return cls(event_type="INTERRUPT", payload={})


# ---------------------------------------------------------------------------
# REST request / response types
# ---------------------------------------------------------------------------

class StartSessionRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=200)


class LessonBlock(BaseModel):
    id: str
    title: str
    difficulty: int = Field(ge=1, le=3)


class LessonPlan(BaseModel):
    topic: str
    blocks: list[LessonBlock]
    current_block: str  # id of active block


class StartSessionResponse(BaseModel):
    session_id: str
    lesson_plan: LessonPlan


class TopicSummary(BaseModel):
    title: str
    duration_seconds: int
    dominant_state: str
    comprehension: Literal["strong", "moderate", "needs_review"]


class AdaptationEvent(BaseModel):
    timestamp: float
    from_state: str
    to_state: str
    strategy_applied: str


class SessionSummary(BaseModel):
    duration_seconds: int
    state_breakdown: dict[str, int]  # state -> seconds
    topics: list[TopicSummary]
    adaptation_events: list[AdaptationEvent]
    narrative: str = ""


class StopSessionResponse(BaseModel):
    summary: SessionSummary
