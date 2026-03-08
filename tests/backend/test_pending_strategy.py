"""
Tests for the pending strategy mechanism.

When the speaker lock is held (TTS/response generation in progress),
the EEG planner writes to pending_strategy instead of current_strategy.
After the speaker completes, apply_pending_strategy() promotes it.

This prevents strategy mutations from corrupting an in-progress response.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src" / "backend"))

from session.store import SessionStore, SessionStrategy


@pytest.fixture
def store():
    return SessionStore()


@pytest.fixture
def session(store):
    return store.create(topic="calculus", lesson_plan={"blocks": []})


@pytest.mark.asyncio
async def test_pending_strategy_set_while_lock_held(store, session):
    """Strategy update while speaker is active should go to pending, not current."""
    sid = session.session_id
    new_strategy = SessionStrategy(strategy="step_by_step", tone="slow")

    # Acquire speaker lock
    async with session.speaker_lock:
        # Simulate planner update mid-response
        session.pending_strategy = new_strategy
        # current_strategy NOT changed yet
        assert session.current_strategy.strategy == "continue"

    # After lock released, pending_strategy still set
    assert session.pending_strategy is not None
    assert session.pending_strategy.strategy == "step_by_step"


@pytest.mark.asyncio
async def test_pending_strategy_applied_after_speaker_completes(store, session):
    """apply_pending_strategy() promotes pending to current and clears pending."""
    sid = session.session_id
    session.pending_strategy = SessionStrategy(strategy="re_engage", tone="encouraging")

    applied = await store.apply_pending_strategy(sid)

    assert applied is True
    assert session.current_strategy.strategy == "re_engage"
    assert session.current_strategy.tone == "encouraging"
    assert session.pending_strategy is None


@pytest.mark.asyncio
async def test_pending_strategy_only_latest_wins(store, session):
    """If planner updates pending_strategy multiple times, only last survives."""
    sid = session.session_id

    # Simulate two rapid planner updates while speaker is active
    session.pending_strategy = SessionStrategy(strategy="step_by_step", tone="slow")
    session.pending_strategy = SessionStrategy(strategy="re_engage", tone="encouraging")

    await store.apply_pending_strategy(sid)

    assert session.current_strategy.strategy == "re_engage"


@pytest.mark.asyncio
async def test_apply_pending_returns_false_when_none(store, session):
    """apply_pending_strategy() is a no-op when no pending update exists."""
    sid = session.session_id
    assert session.pending_strategy is None

    applied = await store.apply_pending_strategy(sid)

    assert applied is False
    assert session.current_strategy.strategy == "continue"


@pytest.mark.asyncio
async def test_apply_pending_returns_false_for_missing_session(store):
    """apply_pending_strategy() returns False gracefully for unknown session."""
    applied = await store.apply_pending_strategy("nonexistent-id")
    assert applied is False
