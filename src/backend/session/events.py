"""
Session event log (event sourcing for business-state transitions).

Records business events only — NOT raw EEG samples.
Events: session_started, session_stopped, eeg_connected, eeg_disconnected,
        state_changed, state_published, strategy_updated.

The event log provides an audit trail of the adaptive loop for
post-session analysis and the adaptation_events summary field.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SessionEvent:
    event_type: str
    session_id: str
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class SessionEventLog:
    """
    Append-only in-memory event log per session.

    Usage:
        log = SessionEventLog()
        log.record("session_started", "sess-abc", {"topic": "derivatives"})
        log.record("state_changed", "sess-abc", {"from": "FOCUSED", "to": "OVERLOADED"})
        events = log.get_events("sess-abc")
    """

    def __init__(self) -> None:
        self._log: list[SessionEvent] = []

    def record(
        self,
        event_type: str,
        session_id: str,
        data: dict[str, Any] | None = None,
    ) -> SessionEvent:
        event = SessionEvent(
            event_type=event_type,
            session_id=session_id,
            data=data or {},
        )
        self._log.append(event)
        logger.debug("Event: %s [%s] %s", event_type, session_id, data)
        return event

    def get_events(
        self,
        session_id: str,
        event_type: str | None = None,
    ) -> list[SessionEvent]:
        events = [e for e in self._log if e.session_id == session_id]
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return events

    def get_state_transitions(self, session_id: str) -> list[dict]:
        """
        Return adaptation events for post-session summary.
        Matches AdaptationEvent schema.
        """
        events = self.get_events(session_id, "state_published")
        result = []
        for i, e in enumerate(events):
            if i == 0:
                continue
            result.append({
                "timestamp": e.timestamp,
                "from_state": events[i - 1].data.get("state", ""),
                "to_state": e.data.get("state", ""),
                "strategy_applied": e.data.get("strategy", ""),
            })
        return result


# Module-level singleton
event_log = SessionEventLog()
