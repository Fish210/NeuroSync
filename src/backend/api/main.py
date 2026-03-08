"""
NeuroSync FastAPI application entry point.

Startup sequence:
    1. Load config from environment / .env file
    2. Mount CORS middleware (allow localhost:3000)
    3. Include REST router
    4. Mount WebSocket endpoint
    5. Start EEG ingestion thread on lifespan startup (Phase 1)

Run with:
    cd src/backend
    uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

# Load .env before anything else
load_dotenv(dotenv_path="../../config/backend/.env", override=False)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
BACKEND_HOST = os.getenv("BACKEND_HOST", "127.0.0.1")
BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8000"))

# Global EEG ingestion + watchdog handles (set in lifespan)
_eeg_ingestion = None
_eeg_watchdog_task: asyncio.Task | None = None
_eeg_queue: asyncio.Queue | None = None
_active_session_id: str | None = None  # Phase 1: single-session model
_last_planner_trigger: float = 0.0        # timestamp of last planner strategy update
PLANNER_COOLDOWN_SECONDS: float = 10.0    # minimum seconds between planner updates


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start EEG pipeline on startup, stop on shutdown."""
    global _eeg_ingestion, _eeg_watchdog_task, _eeg_queue

    logger.info("NeuroSync backend starting up")

    # Create async queue bridging ingestion thread → event loop
    _eeg_queue = asyncio.Queue(maxsize=256)

    # Start EEG ingestion in background (non-blocking — connects to LSL lazily)
    loop = asyncio.get_event_loop()

    from eeg.ingestion import EEGIngestion
    _eeg_ingestion = EEGIngestion(loop=loop, queue=_eeg_queue)
    _eeg_ingestion.start()

    # Start watchdog
    from eeg.watchdog import EEGWatchdog
    watchdog = EEGWatchdog(
        get_last_packet_time=lambda: _eeg_ingestion.last_packet_time,
        on_disconnect=_on_eeg_disconnect,
        on_reconnect=_on_eeg_reconnect,
    )
    _eeg_watchdog_task = asyncio.create_task(watchdog.run())

    # Start EEG event processor
    asyncio.create_task(_process_eeg_queue())

    logger.info("EEG pipeline started. Waiting for Muse LSL stream...")

    yield  # Application runs here

    # Shutdown
    logger.info("Shutting down EEG pipeline")
    if _eeg_watchdog_task:
        _eeg_watchdog_task.cancel()
    if _eeg_ingestion:
        _eeg_ingestion.stop()
    logger.info("NeuroSync backend stopped")


async def _on_eeg_disconnect() -> None:
    """Called by watchdog when EEG stream goes silent."""
    from api.models import SessionEventPayload, WebSocketEnvelope
    from api.websocket import manager
    if _active_session_id:
        await manager.broadcast(
            _active_session_id,
            WebSocketEnvelope.session_event(
                SessionEventPayload(type="eeg_disconnected")
            ),
        )


async def _on_eeg_reconnect() -> None:
    """Called by watchdog when EEG stream resumes."""
    from api.models import SessionEventPayload, WebSocketEnvelope
    from api.websocket import manager
    if _active_session_id:
        await manager.broadcast(
            _active_session_id,
            WebSocketEnvelope.session_event(
                SessionEventPayload(type="eeg_reconnected")
            ),
        )


async def _process_eeg_queue() -> None:
    """
    Consume events from the EEG ingestion queue and process them.
    Runs as an asyncio task — never blocks the event loop.

    Event types from ingestion thread:
        eeg_connected    → SESSION_EVENT to frontend
        eeg_disconnected → SESSION_EVENT to frontend (also handled by watchdog)
        eeg_data         → trigger processing window if enough samples
        contact_quality  → SESSION_EVENT to frontend
    """
    global _active_session_id, _last_planner_trigger

    from api.models import (
        EEGBandPowers, SessionEventPayload, StateUpdatePayload, WebSocketEnvelope
    )
    from api.routes import record_state_for_session
    from api.websocket import manager
    from eeg.classifier import CognitiveStateClassifier
    from eeg.filter import BandPowerSmoother, DwellTimeFilter
    from eeg.processor import EEGProcessor
    from session.store import session_store

    processor = EEGProcessor()
    smoother = BandPowerSmoother()
    classifier = CognitiveStateClassifier()
    dwell_filter = DwellTimeFilter()

    logger.info("EEG queue processor started")

    while True:
        try:
            event = await asyncio.wait_for(_eeg_queue.get(), timeout=5.0)
        except asyncio.TimeoutError:
            continue
        except asyncio.CancelledError:
            return

        event_type = event.get("type", "")

        if event_type == "eeg_connected":
            logger.info("EEG stream connected")
            if _active_session_id:
                await manager.broadcast(
                    _active_session_id,
                    WebSocketEnvelope.session_event(
                        SessionEventPayload(type="eeg_connected")
                    ),
                )

        elif event_type == "eeg_data":
            # Process latest samples from ring buffer
            if not _eeg_ingestion:
                continue

            samples = _eeg_ingestion.get_recent_samples(512)
            raw_powers = processor.compute(samples)
            if raw_powers is None:
                continue

            smoothed = smoother.update(raw_powers)

            # Feed to classifier (also adds to calibrator if warming up)
            result = classifier.classify(smoothed)

            # Dwell-time filter — only act on confirmed state transitions
            published_state = dwell_filter.update(result.state)

            # Always broadcast band power update (even without state transition)
            if _active_session_id:
                bands = EEGBandPowers(
                    alpha=smoothed.alpha,
                    beta=smoothed.beta,
                    theta=smoothed.theta,
                    gamma=smoothed.gamma,
                    delta=smoothed.delta,
                )
                payload = StateUpdatePayload(
                    state=result.state,
                    confidence=result.confidence,
                    bands=bands,
                )
                await manager.broadcast(
                    _active_session_id,
                    WebSocketEnvelope.state_update(payload),
                )

                if published_state:
                    record_state_for_session(_active_session_id, published_state)
                    # Fix: keep session.current_state in sync for speaker agent
                    await session_store.update_state(_active_session_id, published_state)
                    # Trigger planner strategy update with cooldown
                    _now = time.time()
                    if _now - _last_planner_trigger >= PLANNER_COOLDOWN_SECONDS:
                        _last_planner_trigger = _now
                        from agents.planner import update_strategy_for_state
                        asyncio.create_task(
                            update_strategy_for_state(_active_session_id, published_state)
                        )

        elif event_type == "contact_quality":
            if _active_session_id:
                await manager.broadcast(
                    _active_session_id,
                    WebSocketEnvelope.session_event(
                        SessionEventPayload(
                            type="contact_quality",
                            data=event.get("data", {}),
                        )
                    ),
                )

        elif event_type == "eeg_disconnected":
            if _active_session_id:
                await manager.broadcast(
                    _active_session_id,
                    WebSocketEnvelope.session_event(
                        SessionEventPayload(type="eeg_disconnected")
                    ),
                )


# Create FastAPI app
app = FastAPI(
    title="NeuroSync Backend",
    description="Neuroadaptive AI tutoring backend",
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS — must be added before routes ──────────────────────────────────────
# Allow frontend dev server (localhost:3000) and production origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN, "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── REST routes ──────────────────────────────────────────────────────────────
from api.routes import router  # noqa: E402
app.include_router(router)


# ── WebSocket endpoint ───────────────────────────────────────────────────────
@app.websocket("/ws/session/{session_id}")
async def ws_endpoint(websocket: WebSocket, session_id: str) -> None:
    global _active_session_id
    _active_session_id = session_id  # Phase 1: track active session for EEG routing
    from api.websocket import handle_websocket
    await handle_websocket(websocket, session_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host=BACKEND_HOST,
        port=BACKEND_PORT,
        reload=True,
        log_level="info",
    )
