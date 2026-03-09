"""
EEG ingestion thread.

Reads EEG and HSI samples from the Muse headband via LSL.
Runs in a dedicated OS thread — never called from the asyncio event loop.
Communicates with the async backend via asyncio.Queue.

Threading model:
    - One ingestion thread per session
    - Thread writes to _ring_buffer (protected by _lock)
    - Thread puts event dicts onto asyncio.Queue via loop.call_soon_threadsafe
    - Async code reads from queue; never touches LSL inlet directly

Simulation mode:
    Set environment variable EEG_SIMULATE=1 (or true/yes) to run without a
    real Muse headband. The ingestion thread will generate synthetic EEG
    samples that cycle through FOCUSED → OVERLOADED → DISENGAGED states
    every ~10 seconds, allowing full end-to-end demo without hardware.
"""
from __future__ import annotations

import asyncio
import collections
import logging
import math
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# Set EEG_SIMULATE=1 to bypass LSL and emit synthetic EEG data for demos
_EEG_SIMULATE_ENV = os.getenv("EEG_SIMULATE", "0").lower()
EEG_SIMULATE = _EEG_SIMULATE_ENV in ("1", "true", "yes")

# Muse 2 / Muse S LSL stream names
EEG_STREAM_TYPE = "EEG"
HSI_STREAM_TYPE = "Markers"  # Muse headband status indicator stream name
HSI_STREAM_NAME = "Muse"

# Number of EEG samples to keep in ring buffer (at 256 Hz, 512 = 2 seconds)
RING_BUFFER_SIZE = 512

# Number of EEG channels on Muse 2 (TP9, AF7, AF8, TP10 + AUX)
EEG_CHANNEL_COUNT = 5

# HSI channel indices (contact quality, 1.0=good, >1.5=poor)
HSI_CHANNELS = {"TP9": 0, "AF7": 1, "AF8": 2, "TP10": 3}

# HSI threshold: values above this are "poor" contact
HSI_POOR_THRESHOLD = 1.5


@dataclass
class EEGSample:
    """A single EEG sample from the Muse headband."""
    channels: np.ndarray  # shape (5,) — TP9, AF7, AF8, TP10, AUX
    timestamp: float      # LSL timestamp


@dataclass
class IngestionState:
    """Thread-safe state shared between ingestion thread and async layer."""
    ring_buffer: collections.deque = field(
        default_factory=lambda: collections.deque(maxlen=RING_BUFFER_SIZE)
    )
    lock: threading.Lock = field(default_factory=threading.Lock)
    last_packet_time: float = field(default_factory=time.time)
    contact_quality: dict[str, float] = field(
        default_factory=lambda: {"TP9": 0.0, "AF7": 0.0, "AF8": 0.0, "TP10": 0.0}
    )


class EEGIngestion:
    """
    Muse EEG ingestion thread.

    Usage:
        loop = asyncio.get_event_loop()
        queue = asyncio.Queue()
        ingestion = EEGIngestion(loop, queue)
        ingestion.start()
        # ... later ...
        ingestion.stop()
    """

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        queue: asyncio.Queue,
        stream_timeout: float = 10.0,
        pull_timeout: float = 0.05,
        pull_max_samples: int = 32,
    ) -> None:
        self._loop = loop
        self._queue = queue
        self._stream_timeout = stream_timeout
        self._pull_timeout = pull_timeout
        self._pull_max_samples = pull_max_samples

        self._state = IngestionState()
        self._running = False
        self._thread: threading.Thread | None = None
        self._is_connected: bool = False

    def start(self) -> None:
        """Start the ingestion thread. Call once per session."""
        if self._thread and self._thread.is_alive():
            logger.warning("EEGIngestion.start() called while already running")
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run,
            name="eeg-ingestion",
            daemon=True,
        )
        self._thread.start()
        logger.info("EEG ingestion thread started")

    def stop(self) -> None:
        """Signal the ingestion thread to stop and wait for it."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3.0)
        logger.info("EEG ingestion thread stopped")

    @property
    def last_packet_time(self) -> float:
        return self._state.last_packet_time

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    def get_recent_samples(self, n: int = 512) -> list[EEGSample]:
        """Thread-safe snapshot of the most recent n samples."""
        with self._state.lock:
            samples = list(self._state.ring_buffer)
        return samples[-n:] if len(samples) > n else samples

    def get_contact_quality(self) -> dict[str, float]:
        with self._state.lock:
            return dict(self._state.contact_quality)

    # ------------------------------------------------------------------
    # Private: ingestion thread
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """Main ingestion loop. Runs in dedicated thread."""
        if EEG_SIMULATE:
            logger.info("EEG simulation mode active — no Muse hardware required")
            self._run_simulated()
            return

        try:
            inlet = self._resolve_eeg_stream()
        except RuntimeError as exc:
            logger.error("Failed to find EEG stream: %s", exc)
            self._is_connected = False
            self._emit({"type": "eeg_disconnected", "reason": str(exc)})
            return

        self._is_connected = True
        self._emit({"type": "eeg_connected"})
        logger.info("EEG inlet connected")

        while self._running:
            self._pull_eeg(inlet)

    # Simulation interval in seconds (emit a new synthetic window this often)
    _SIM_INTERVAL: float = 0.125  # ~8 Hz, matching muselsl chunk rate

    def _run_simulated(self) -> None:
        """
        Emit synthetic EEG samples that cycle FOCUSED → OVERLOADED → DISENGAGED.
        Each state lasts ~10 seconds (80 windows × 0.125 s), giving the frontend
        enough time to observe the adaptive response before the next state flip.

        Signal characteristics per state (relative band powers):
            FOCUSED:    high beta, moderate alpha, low theta
            OVERLOADED: high beta+gamma, suppressed alpha
            DISENGAGED: high theta+alpha, low beta
        """
        SAMPLE_RATE = 256.0
        CHUNK_SAMPLES = 32  # emit 32 samples per interval (matching real pull_max)
        STATE_CYCLE = ["FOCUSED", "OVERLOADED", "DISENGAGED"]
        WINDOWS_PER_STATE = 80  # ~10 seconds at 0.125 s intervals

        # Band-power targets per state [delta, theta, alpha, beta, gamma]
        # Values are the dominant amplitude in µV for each band injection
        _STATE_PARAMS: dict[str, dict] = {
            "FOCUSED":    {"beta_amp": 8.0,  "theta_amp": 2.0, "alpha_amp": 5.0,  "gamma_amp": 2.0},
            "OVERLOADED": {"beta_amp": 10.0, "theta_amp": 3.0, "alpha_amp": 1.5,  "gamma_amp": 7.0},
            "DISENGAGED": {"beta_amp": 2.0,  "theta_amp": 8.0, "alpha_amp": 9.0,  "gamma_amp": 1.0},
        }

        self._is_connected = True
        self._emit({"type": "eeg_connected"})
        logger.info("Simulated EEG stream connected")

        state_idx = 0
        window_count = 0
        t = 0.0  # running time index

        while self._running:
            state = STATE_CYCLE[state_idx % len(STATE_CYCLE)]
            params = _STATE_PARAMS[state]

            # Generate CHUNK_SAMPLES synthetic EEG samples (4 channels)
            samples: list = []
            timestamps: list = []
            for _ in range(CHUNK_SAMPLES):
                ts = t / SAMPLE_RATE
                # Mix sinusoids at band centre frequencies + small noise
                beta_sig   = params["beta_amp"]  * math.sin(2 * math.pi * 20.0 * ts)
                theta_sig  = params["theta_amp"] * math.sin(2 * math.pi * 6.0  * ts)
                alpha_sig  = params["alpha_amp"] * math.sin(2 * math.pi * 10.0 * ts)
                gamma_sig  = params["gamma_amp"] * math.sin(2 * math.pi * 40.0 * ts)
                noise = float(np.random.normal(0, 0.5))
                val = beta_sig + theta_sig + alpha_sig + gamma_sig + noise
                # 4 EEG channels + 1 AUX = 5 channels
                samples.append([val, val * 0.95, val * 1.05, val * 0.98, 0.0])
                timestamps.append(time.time())
                t += 1.0

            now = time.time()
            with self._state.lock:
                self._state.last_packet_time = now
                for sample, ts in zip(samples, timestamps):
                    arr = np.asarray(sample, dtype=np.float32)
                    self._state.ring_buffer.append(EEGSample(channels=arr, timestamp=ts))

            self._emit({"type": "eeg_data", "count": len(samples)})

            window_count += 1
            if window_count >= WINDOWS_PER_STATE:
                window_count = 0
                state_idx += 1
                next_state = STATE_CYCLE[state_idx % len(STATE_CYCLE)]
                logger.info("EEG simulation: transitioning to state %s", next_state)

            time.sleep(self._SIM_INTERVAL)

    def _resolve_eeg_stream(self):
        """Resolve LSL EEG stream. Raises RuntimeError on timeout."""
        from pylsl import StreamInlet, resolve_stream

        logger.info("Searching for EEG LSL stream (timeout=%.1fs)...", self._stream_timeout)
        streams = resolve_stream("type", EEG_STREAM_TYPE, timeout=self._stream_timeout)
        if not streams:
            raise RuntimeError(
                f"No EEG LSL stream found after {self._stream_timeout}s. "
                "Is muselsl running? (muselsl stream --address XX:XX:XX:XX:XX:XX)"
            )
        inlet = StreamInlet(streams[0], max_chunklen=self._pull_max_samples)
        logger.info("EEG stream resolved: %s", streams[0].name())
        return inlet

    def _pull_eeg(self, inlet) -> None:
        """Pull a chunk of EEG samples and append to ring buffer."""
        try:
            samples, timestamps = inlet.pull_chunk(
                max_samples=self._pull_max_samples,
                timeout=self._pull_timeout,
            )
        except Exception as exc:  # pylsl can raise on disconnection
            logger.warning("LSL pull_chunk error: %s", exc)
            return

        if not samples:
            return  # timeout with no data — watchdog handles stale detection

        now = time.time()
        with self._state.lock:
            self._state.last_packet_time = now
            for sample, ts in zip(samples, timestamps):
                arr = np.asarray(sample, dtype=np.float32)
                self._state.ring_buffer.append(EEGSample(channels=arr, timestamp=ts))

        # Check HSI contact quality (every 32 samples ~ 0.125 seconds)
        self._update_contact_quality(samples)

        # Notify async layer that new samples are available
        self._emit({"type": "eeg_data", "count": len(samples)})

    def _update_contact_quality(self, samples: list) -> None:
        """
        Muse headband embeds HSI contact quality in channels 5-8 of certain
        stream configurations. For muselsl raw EEG stream, HSI may be in a
        separate 'Markers' stream. Here we estimate contact quality from the
        EEG amplitude variance as a proxy: high variance = likely poor contact.

        For production, subscribe to the HSI LSL stream separately.
        Values near 1.0 = good contact, >1.5 = poor contact (Muse convention).
        """
        if len(samples) < 4:
            return

        arr = np.asarray(samples, dtype=np.float32)  # shape (N, channels)
        if arr.shape[1] < 4:
            return

        # Use amplitude variance as proxy for contact quality
        # High std dev (>50 µV) indicates noise / poor contact
        stds = arr[:, :4].std(axis=0)  # TP9, AF7, AF8, TP10
        quality = {}
        for name, idx in HSI_CHANNELS.items():
            # Map std to HSI-like scale: 1.0=good (<20µV), 2.0=poor (>80µV)
            normalized = 1.0 + max(0.0, (float(stds[idx]) - 20.0) / 60.0)
            quality[name] = round(min(normalized, 3.0), 3)

        with self._state.lock:
            self._state.contact_quality = quality

        overall = (
            "poor"
            if any(v > HSI_POOR_THRESHOLD for v in quality.values())
            else "good"
        )

        if overall == "poor":
            self._emit({
                "type": "contact_quality",
                "data": {**quality, "overall": overall},
            })

    def _emit(self, event: dict[str, Any]) -> None:
        """Thread-safe: put event on asyncio.Queue from the ingestion thread."""
        asyncio.run_coroutine_threadsafe(
            self._queue.put(event),
            self._loop,
        )
