"""
Server-side Voice Activity Detection.

Receives audio signal level from the browser (0.0–1.0) every 100ms.
Detects barge-in: N consecutive readings above threshold → interrupt TTS.

One VoiceActivityDetector instance per session, managed by the WebSocket hub.

Usage:
    vad = VoiceActivityDetector()
    barge_in = vad.update(level)
    if barge_in:
        # cancel TTS, send INTERRUPT
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

# Signal level above which speech is detected (0.0–1.0)
VAD_THRESHOLD = float(os.getenv("VAD_THRESHOLD", "0.6"))

# Number of consecutive above-threshold readings to confirm barge-in
VAD_CONSECUTIVE = int(os.getenv("VAD_CONSECUTIVE", "3"))


class VoiceActivityDetector:
    """
    Stateful barge-in detector.

    Fires once per barge-in event (resets after student goes silent).
    """

    def __init__(
        self,
        threshold: float = VAD_THRESHOLD,
        consecutive: int = VAD_CONSECUTIVE,
    ) -> None:
        self._threshold = threshold
        self._consecutive = consecutive
        self._count = 0         # consecutive above-threshold readings
        self._barge_in_active = False  # True while student is speaking

    def update(self, level: float) -> bool:
        """
        Update with a new signal level reading.

        Returns True exactly once when barge-in is first detected.
        Returns False on all subsequent readings until student goes silent.
        """
        if level > self._threshold:
            self._count += 1
        else:
            self._count = 0
            self._barge_in_active = False  # reset after silence

        if self._count >= self._consecutive and not self._barge_in_active:
            self._barge_in_active = True
            logger.info("VAD barge-in detected (level=%.2f)", level)
            return True

        return False

    def reset(self) -> None:
        """Reset state, e.g., when TTS is not active."""
        self._count = 0
        self._barge_in_active = False
