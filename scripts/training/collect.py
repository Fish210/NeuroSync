"""
EEG data collector for training sessions.

Runs a background thread reading from a muselsl LSL stream.
Call start_phase(label) / end_phase() to capture labeled windows.
No asyncio — standalone use only.
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import numpy as np

# Allow importing from src/backend/eeg without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src" / "backend"))

from eeg.ingestion import EEGSample  # noqa: E402

PULL_MAX_SAMPLES = 32
PULL_TIMEOUT = 0.05
STREAM_TIMEOUT = 15.0


class EEGCollector:
    """
    Threaded EEG collector.

    Usage:
        collector = EEGCollector()
        collector.start()                        # connects to LSL stream
        collector.start_phase("FOCUSED")         # begin labeling
        time.sleep(90)
        samples = collector.end_phase()          # stop labeling, get samples
        collector.stop()
    """

    def __init__(self) -> None:
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

        # Current phase capture
        self._current_label: str | None = None
        self._phase_buffer: list[EEGSample] = []

        # Full labeled dataset: list of (label, samples)
        self._dataset: list[tuple[str, list[EEGSample]]] = []

        self._inlet = None
        self._connected = threading.Event()
        self._error: str | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start background collection thread. Blocks until LSL connected or error."""
        self._running = True
        self._thread = threading.Thread(target=self._run, name="eeg-collect", daemon=True)
        self._thread.start()
        # Wait up to STREAM_TIMEOUT for connection
        if not self._connected.wait(timeout=STREAM_TIMEOUT + 2):
            raise RuntimeError("Timed out waiting for EEG LSL stream. Is muselsl running?")
        if self._error:
            raise RuntimeError(self._error)

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=3.0)

    def start_phase(self, label: str) -> None:
        """Start capturing samples for a labeled phase."""
        with self._lock:
            self._current_label = label
            self._phase_buffer = []

    def end_phase(self) -> list[EEGSample]:
        """Stop capturing, save phase to dataset, return captured samples."""
        with self._lock:
            samples = list(self._phase_buffer)
            label = self._current_label
            self._current_label = None
            self._phase_buffer = []

        if label and samples:
            self._dataset.append((label, samples))

        return samples

    def get_dataset(self) -> list[tuple[str, list[EEGSample]]]:
        """Return all collected (label, samples) pairs."""
        return list(self._dataset)

    def sample_count(self) -> int:
        """Current phase sample count (thread-safe)."""
        with self._lock:
            return len(self._phase_buffer)

    # ------------------------------------------------------------------
    # Private: background thread
    # ------------------------------------------------------------------

    def _run(self) -> None:
        try:
            self._inlet = self._connect()
        except RuntimeError as exc:
            self._error = str(exc)
            self._connected.set()
            return

        self._connected.set()

        while self._running:
            self._pull()

    def _connect(self):
        from pylsl import StreamInlet, resolve_stream
        streams = resolve_stream("type", "EEG", timeout=STREAM_TIMEOUT)
        if not streams:
            raise RuntimeError(
                f"No EEG LSL stream found after {STREAM_TIMEOUT}s.\n"
                "Run: muselsl stream --address XX:XX:XX:XX:XX:XX"
            )
        return StreamInlet(streams[0], max_chunklen=PULL_MAX_SAMPLES)

    def _pull(self) -> None:
        try:
            samples, timestamps = self._inlet.pull_chunk(
                max_samples=PULL_MAX_SAMPLES,
                timeout=PULL_TIMEOUT,
            )
        except Exception:
            return

        if not samples:
            return

        with self._lock:
            if self._current_label is not None:
                for sample, ts in zip(samples, timestamps):
                    arr = np.asarray(sample, dtype=np.float32)
                    self._phase_buffer.append(EEGSample(channels=arr, timestamp=ts))
