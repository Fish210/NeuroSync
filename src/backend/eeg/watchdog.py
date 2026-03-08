"""
EEG BLE watchdog.

Monitors the EEG ingestion thread's last_packet_timestamp.
If no EEG samples arrive for longer than WATCHDOG_TIMEOUT seconds,
emits a SESSION_EVENT { type: 'eeg_disconnected' } to the WebSocket.

Runs as an asyncio background task (not a thread) — uses asyncio.sleep.

Why this matters:
    muselsl does NOT reliably detect Bluetooth disconnection. The inlet
    may hang silently. Without this watchdog, the cognitive state freezes
    and no adaptation fires — the demo appears broken without any error.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Callable

logger = logging.getLogger(__name__)

# How long without a packet before declaring disconnected (seconds)
WATCHDOG_TIMEOUT = float(os.getenv("EEG_WATCHDOG_TIMEOUT", "2.0"))

# How often the watchdog polls (seconds)
WATCHDOG_POLL_INTERVAL = 0.5


class EEGWatchdog:
    """
    Async watchdog task for EEG Bluetooth connection health.

    Usage:
        watchdog = EEGWatchdog(
            get_last_packet_time=ingestion.last_packet_time,
            on_disconnect=lambda: queue.put_nowait({"type": "eeg_disconnected"}),
            on_reconnect=lambda: queue.put_nowait({"type": "eeg_reconnected"}),
        )
        task = asyncio.create_task(watchdog.run())
        # ...
        task.cancel()
    """

    def __init__(
        self,
        get_last_packet_time: Callable[[], float],
        on_disconnect: Callable,
        on_reconnect: Callable,
        timeout: float = WATCHDOG_TIMEOUT,
        poll_interval: float = WATCHDOG_POLL_INTERVAL,
    ) -> None:
        self._get_last_packet_time = get_last_packet_time
        self._on_disconnect = on_disconnect
        self._on_reconnect = on_reconnect
        self._timeout = timeout
        self._poll_interval = poll_interval
        self._disconnected = False

    async def run(self) -> None:
        """Main watchdog loop. Cancel this task to stop."""
        logger.info("EEG watchdog started (timeout=%.1fs)", self._timeout)

        while True:
            try:
                await asyncio.sleep(self._poll_interval)
                age = time.time() - self._get_last_packet_time()

                if age > self._timeout and not self._disconnected:
                    self._disconnected = True
                    logger.warning(
                        "EEG disconnected: no packets for %.1fs", age
                    )
                    await self._safe_call(self._on_disconnect)

                elif age <= self._timeout and self._disconnected:
                    self._disconnected = False
                    logger.info("EEG reconnected")
                    await self._safe_call(self._on_reconnect)

            except asyncio.CancelledError:
                logger.info("EEG watchdog cancelled")
                return
            except Exception as exc:
                logger.error("EEG watchdog error: %s", exc, exc_info=True)

    @staticmethod
    async def _safe_call(fn: Callable) -> None:
        """Call fn whether it is sync or async."""
        import inspect
        if inspect.iscoroutinefunction(fn):
            await fn()
        else:
            fn()
