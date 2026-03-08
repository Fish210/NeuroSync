"""
Speaker lock helpers.

Each session has its own speaker_lock (asyncio.Lock) on SessionData.
This module provides a context manager for clean acquire/release.

Usage:
    async with speaker_running(session_id):
        # planner cannot mutate strategy here
        response = await speaker.generate_response(...)
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from session.store import session_store


@asynccontextmanager
async def speaker_running(session_id: str):
    """Acquire the per-session speaker lock for the duration of a speaker call."""
    session = session_store.require(session_id)
    async with session.speaker_lock:
        yield
        # After speaker completes, apply any pending strategy update from planner
        await session_store.apply_pending_strategy(session_id)
