"""
EEG state filter.

Applies two layers of filtering before publishing cognitive state:

1. EMA (Exponential Moving Average) smoothing on band powers
   Reduces noise from individual FFT windows.
   alpha=0.3 means new value contributes 30% to the smoothed estimate.

2. Dwell-time filter on classified state
   Requires DWELL_REQUIRED consecutive windows in the same state before
   publishing a state transition. This prevents EEG artifacts from
   triggering spurious planner calls.

   Example: if DWELL_REQUIRED=3, the system must see OVERLOADED three
   times in a row before publishing OVERLOADED to the WebSocket.
"""
from __future__ import annotations

import logging
import os

from eeg.processor import BandPowers

logger = logging.getLogger(__name__)

# EMA smoothing factor: 0.0 = no update, 1.0 = no smoothing
EMA_ALPHA = float(os.getenv("EEG_EMA_ALPHA", "0.3"))

# Number of consecutive windows required to confirm a state transition
DWELL_REQUIRED = int(os.getenv("EEG_DWELL_WINDOWS", "3"))


class BandPowerSmoother:
    """
    Applies EMA smoothing to band powers.
    Maintains a running smoothed estimate updated on each new window.
    """

    def __init__(self, alpha: float = EMA_ALPHA) -> None:
        self._alpha = alpha
        self._smoothed: BandPowers | None = None

    def update(self, powers: BandPowers) -> BandPowers:
        """
        Update smoothed estimate with new window. Returns smoothed BandPowers.
        """
        if self._smoothed is None:
            self._smoothed = powers
            return powers

        s = self._smoothed
        a = self._alpha

        smoothed = BandPowers(
            delta=a * powers.delta + (1 - a) * s.delta,
            theta=a * powers.theta + (1 - a) * s.theta,
            alpha=a * powers.alpha + (1 - a) * s.alpha,
            beta=a * powers.beta + (1 - a) * s.beta,
            gamma=a * powers.gamma + (1 - a) * s.gamma,
            timestamp=powers.timestamp,
        )
        self._smoothed = smoothed
        return smoothed

    def reset(self) -> None:
        self._smoothed = None


class DwellTimeFilter:
    """
    Prevents state transitions from firing until a state is stable for
    DWELL_REQUIRED consecutive processing windows.

    State machine:
        candidate_state: the state being considered for transition
        candidate_count: how many consecutive windows have shown candidate_state
        published_state: the last state that was officially published

    A state change fires only when candidate_count reaches DWELL_REQUIRED.
    """

    def __init__(self, dwell_required: int = DWELL_REQUIRED) -> None:
        self._dwell_required = dwell_required
        self._candidate_state: str | None = None
        self._candidate_count: int = 0
        self._published_state: str | None = None

    @property
    def current_published_state(self) -> str | None:
        return self._published_state

    def update(self, new_state: str) -> str | None:
        """
        Feed a new classified state into the filter.

        Returns:
            The new state to publish if a transition occurred, else None.
        """
        if new_state == self._candidate_state:
            self._candidate_count += 1
        else:
            # New candidate — reset counter
            self._candidate_state = new_state
            self._candidate_count = 1

        if self._candidate_count >= self._dwell_required:
            if new_state != self._published_state:
                old_state = self._published_state
                self._published_state = new_state
                logger.info(
                    "State transition: %s → %s (after %d windows)",
                    old_state,
                    new_state,
                    self._candidate_count,
                )
                return new_state  # signal: publish this state change

        return None  # no transition yet

    def reset(self) -> None:
        self._candidate_state = None
        self._candidate_count = 0
        self._published_state = None
