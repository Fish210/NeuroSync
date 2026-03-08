"""
Hume TTS integration.

Calls the Hume REST TTS API, receives MP3 audio bytes,
splits into chunks, and streams them as AUDIO_CHUNK WebSocket messages.

The returned asyncio.Task can be cancelled to stop mid-stream
(used by VAD barge-in detection).

Usage:
    task = asyncio.create_task(
        synthesize_and_stream(text, session_id, manager)
    )
    # Later, to interrupt:
    task.cancel()
"""
from __future__ import annotations

import asyncio
import base64
import logging
import os
import time

import httpx

logger = logging.getLogger(__name__)

HUME_API_KEY = os.getenv("HUME_API_KEY", "")
HUME_TTS_URL = os.getenv("HUME_TTS_URL", "https://api.hume.ai/v0/tts")
HUME_VOICE_NAME = os.getenv("HUME_VOICE_NAME", "KORA")

# Size of each audio chunk sent over WebSocket (bytes)
CHUNK_BYTES = 4096


async def synthesize_and_stream(
    text: str,
    session_id: str,
    ws_manager,
) -> None:
    """
    Synthesize text with Hume TTS and stream audio chunks over WebSocket.

    Raises asyncio.CancelledError if cancelled (e.g., by VAD barge-in).
    If HUME_API_KEY is not set, logs a warning and returns without sending audio.
    """
    from api.models import WebSocketEnvelope

    if not HUME_API_KEY:
        logger.warning("HUME_API_KEY not set — skipping TTS for session %s", session_id)
        return

    _tts_start = time.monotonic()
    try:
        audio_bytes = await _call_hume(text)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        if "401" in str(exc) or "403" in str(exc) or "unauthorized" in str(exc).lower():
            logger.error("Hume TTS auth failed — check HUME_API_KEY in config/backend/.env")
        else:
            logger.error("Hume TTS failed: %s", exc)
        return

    # Split into chunks and stream
    chunks = _split_chunks(audio_bytes, CHUNK_BYTES)
    total = len(chunks)

    for idx, chunk in enumerate(chunks):
        # Yield to event loop — allows cancellation to propagate
        await asyncio.sleep(0)

        is_final = idx == total - 1
        envelope = WebSocketEnvelope(
            event_type="AUDIO_CHUNK",
            payload={
                "chunk_index": idx,
                "data": base64.b64encode(chunk).decode(),
                "is_final": is_final,
            },
        )
        await ws_manager.broadcast(session_id, envelope)

    _tts_elapsed = time.monotonic() - _tts_start
    logger.info(
        "TTS: streamed %d chunks (%d bytes) in %.2fs for session %s",
        total, len(audio_bytes), _tts_elapsed, session_id,
    )


async def _call_hume(text: str) -> bytes:
    """Call Hume REST API and return raw audio bytes."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            HUME_TTS_URL,
            headers={
                "X-Hume-Api-Key": HUME_API_KEY,
                "Content-Type": "application/json",
            },
            json={
                "utterances": [
                    {
                        "text": text,
                        "voice": {"name": HUME_VOICE_NAME},
                    }
                ],
                "format": {"type": "mp3"},
            },
        )
        response.raise_for_status()
        return response.content


def _split_chunks(data: bytes, size: int) -> list[bytes]:
    """Split bytes into fixed-size chunks."""
    return [data[i : i + size] for i in range(0, len(data), size)]
