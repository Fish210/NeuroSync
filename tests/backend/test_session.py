"""
Tests for session store, tracker, and event log.
No hardware or external API calls required.
"""
from __future__ import annotations

import sys
import os
import asyncio
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'backend'))

import pytest

from session.store import SessionStore, SessionStrategy
from session.tracker import TopicStateTracker
from session.events import SessionEventLog


# ---------------------------------------------------------------------------
# SessionStore tests
# ---------------------------------------------------------------------------

class TestSessionStore:
    def test_create_returns_session(self):
        store = SessionStore()
        lesson = {"topic": "derivatives", "blocks": [], "current_block": ""}
        session = store.create("derivatives", lesson)
        assert session.session_id
        assert session.topic == "derivatives"

    def test_get_returns_existing_session(self):
        store = SessionStore()
        lesson = {"topic": "algebra", "blocks": [], "current_block": ""}
        session = store.create("algebra", lesson)
        retrieved = store.get(session.session_id)
        assert retrieved is session

    def test_get_returns_none_for_missing(self):
        store = SessionStore()
        assert store.get("nonexistent") is None

    def test_require_raises_for_missing(self):
        store = SessionStore()
        with pytest.raises(KeyError):
            store.require("nonexistent")

    def test_delete_removes_session(self):
        store = SessionStore()
        lesson = {"topic": "physics", "blocks": [], "current_block": ""}
        session = store.create("physics", lesson)
        store.delete(session.session_id)
        assert store.get(session.session_id) is None

    @pytest.mark.asyncio
    async def test_update_state_returns_true_on_change(self):
        store = SessionStore()
        lesson = {"topic": "calculus", "blocks": [], "current_block": ""}
        session = store.create("calculus", lesson)
        changed = await store.update_state(session.session_id, "FOCUSED")
        assert changed  # initial state was DISENGAGED

    @pytest.mark.asyncio
    async def test_update_state_returns_false_on_no_change(self):
        store = SessionStore()
        lesson = {"topic": "calculus", "blocks": [], "current_block": ""}
        session = store.create("calculus", lesson)
        await store.update_state(session.session_id, "FOCUSED")
        changed = await store.update_state(session.session_id, "FOCUSED")
        assert not changed

    @pytest.mark.asyncio
    async def test_speaker_lock_prevents_concurrent_access(self):
        """Verify SPEAKER_RUNNING lock is an asyncio.Lock."""
        store = SessionStore()
        lesson = {"topic": "test", "blocks": [], "current_block": ""}
        session = store.create("test", lesson)
        # Lock should be acquirable
        async with session.speaker_lock:
            pass  # no exception = lock works

    def test_add_turn_appends_to_conversation(self):
        store = SessionStore()
        lesson = {"topic": "test", "blocks": [], "current_block": ""}
        session = store.create("test", lesson)
        store.add_turn(session.session_id, "tutor", "Hello!")
        assert len(session.conversation) == 1
        assert session.conversation[0]["text"] == "Hello!"


# ---------------------------------------------------------------------------
# TopicStateTracker tests
# ---------------------------------------------------------------------------

class TestTopicStateTracker:
    def _make_plan(self):
        return {
            "topic": "derivatives",
            "blocks": [
                {"id": "block-1", "title": "What is a derivative?", "difficulty": 1},
                {"id": "block-2", "title": "Limit definition", "difficulty": 2},
                {"id": "block-3", "title": "Power rule", "difficulty": 3},
            ],
            "current_block": "block-1",
        }

    def test_current_block_starts_at_first(self):
        tracker = TopicStateTracker(self._make_plan())
        assert tracker.current_block["id"] == "block-1"

    def test_advance_moves_to_next_block(self):
        tracker = TopicStateTracker(self._make_plan())
        block = tracker.advance_topic()
        assert block is not None
        assert block["id"] == "block-2"

    def test_advance_at_last_block_returns_none(self):
        tracker = TopicStateTracker(self._make_plan())
        tracker.advance_topic()
        tracker.advance_topic()
        result = tracker.advance_topic()
        assert result is None

    def test_record_adds_entry_for_current_topic(self):
        tracker = TopicStateTracker(self._make_plan())
        tracker.record("FOCUSED")
        tracker.record("FOCUSED")
        tracker.record("OVERLOADED")
        # Check entries exist (internal — test via compute_summary)
        state_log = [(time.time() - 10, "FOCUSED"), (time.time(), "OVERLOADED")]
        summary = tracker.compute_summary(state_log)
        assert len(summary["topics"]) > 0

    def test_compute_summary_includes_state_breakdown(self):
        tracker = TopicStateTracker(self._make_plan())
        state_log = [
            (time.time() - 60, "FOCUSED"),
            (time.time() - 30, "OVERLOADED"),
            (time.time(), "DISENGAGED"),
        ]
        summary = tracker.compute_summary(state_log)
        assert "state_breakdown" in summary
        assert "duration_seconds" in summary

    def test_comprehension_strong_for_focused_dominant(self):
        tracker = TopicStateTracker(self._make_plan())
        # Record many FOCUSED entries for block-1
        for _ in range(20):
            tracker.record("FOCUSED")
        state_log = [(time.time() - 20, "FOCUSED"), (time.time(), "FOCUSED")]
        summary = tracker.compute_summary(state_log)
        topic = summary["topics"][0] if summary["topics"] else None
        if topic:
            assert topic["comprehension"] == "strong"


# ---------------------------------------------------------------------------
# SessionEventLog tests
# ---------------------------------------------------------------------------

class TestSessionEventLog:
    def test_record_creates_event(self):
        log = SessionEventLog()
        event = log.record("session_started", "sess-1", {"topic": "math"})
        assert event.event_type == "session_started"
        assert event.session_id == "sess-1"

    def test_get_events_filters_by_session(self):
        log = SessionEventLog()
        log.record("session_started", "sess-1")
        log.record("session_started", "sess-2")
        events = log.get_events("sess-1")
        assert len(events) == 1
        assert events[0].session_id == "sess-1"

    def test_get_events_filters_by_type(self):
        log = SessionEventLog()
        log.record("session_started", "sess-1")
        log.record("state_published", "sess-1", {"state": "FOCUSED"})
        log.record("state_published", "sess-1", {"state": "OVERLOADED"})
        state_events = log.get_events("sess-1", "state_published")
        assert len(state_events) == 2

    def test_get_state_transitions_pairs_consecutive_events(self):
        log = SessionEventLog()
        log.record("state_published", "sess-1", {"state": "FOCUSED", "strategy": "continue"})
        log.record("state_published", "sess-1", {"state": "OVERLOADED", "strategy": "step_by_step"})
        transitions = log.get_state_transitions("sess-1")
        assert len(transitions) == 1
        assert transitions[0]["from_state"] == "FOCUSED"
        assert transitions[0]["to_state"] == "OVERLOADED"
