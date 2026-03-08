"""
Cognitive state classifier.

Uses heuristic band power ratios to classify EEG into one of three states:
    FOCUSED    — high focus_score, moderate cognitive_load
    OVERLOADED — high cognitive_load
    DISENGAGED — low focus_score, low cognitive_load

IMPORTANT: Uses a RELATIVE baseline calibrated at session start.
Different people have wildly different absolute EEG spectra.
All thresholds are computed as deviations from the individual's baseline.

Thresholds are exposed as environment-adjustable constants so they can be
tweaked between demo runs without code changes.
"""
from __future__ import annotations

import logging
import os
import time
from collections import deque
from dataclasses import dataclass, field

from eeg.processor import BandPowers

logger = logging.getLogger(__name__)

# ── Threshold constants (tune via env vars for demo calibration) ──────────
# focus_score = beta / max(theta, eps)
# Values relative to baseline: 1.0 = same as baseline, 2.0 = double baseline
FOCUS_HIGH_THRESHOLD = float(os.getenv("FOCUS_HIGH_THRESHOLD", "1.4"))
FOCUS_LOW_THRESHOLD = float(os.getenv("FOCUS_LOW_THRESHOLD", "0.7"))

# cognitive_load = beta + gamma (relative to baseline)
LOAD_HIGH_THRESHOLD = float(os.getenv("LOAD_HIGH_THRESHOLD", "1.6"))

# Minimum baseline windows before classification starts
BASELINE_MIN_WINDOWS = int(os.getenv("BASELINE_MIN_WINDOWS", "5"))

# Epsilon to avoid division by zero
EPS = 1e-10


@dataclass
class ClassificationResult:
    state: str  # "FOCUSED" | "OVERLOADED" | "DISENGAGED"
    confidence: float
    focus_score: float
    cognitive_load: float
    relative_to_baseline: bool


class BaselineCalibrator:
    """
    Collects band power windows during the calibration phase and computes
    a per-person baseline. All subsequent classification uses relative
    deviations from this baseline.
    """

    def __init__(self, min_windows: int = BASELINE_MIN_WINDOWS) -> None:
        self._min_windows = min_windows
        self._windows: deque[BandPowers] = deque(maxlen=20)
        self._baseline: dict[str, float] | None = None

    @property
    def is_ready(self) -> bool:
        return self._baseline is not None

    @property
    def windows_collected(self) -> int:
        return len(self._windows)

    def add_window(self, powers: BandPowers) -> bool:
        """
        Add a calibration window. Returns True when baseline is ready.
        """
        self._windows.append(powers)

        if len(self._windows) >= self._min_windows and not self._baseline:
            self._compute_baseline()
            return True
        return False

    def _compute_baseline(self) -> None:
        """Average band powers across all calibration windows."""
        n = len(self._windows)
        self._baseline = {
            "alpha": sum(w.alpha for w in self._windows) / n,
            "beta": sum(w.beta for w in self._windows) / n,
            "theta": sum(w.theta for w in self._windows) / n,
            "gamma": sum(w.gamma for w in self._windows) / n,
            "delta": sum(w.delta for w in self._windows) / n,
        }
        logger.info("EEG baseline calibrated: %s", self._baseline)

    def get_baseline(self) -> dict[str, float] | None:
        return self._baseline

    def normalize(self, powers: BandPowers) -> dict[str, float]:
        """
        Return band powers as ratios relative to baseline.
        1.0 = same as baseline, 2.0 = double baseline, 0.5 = half baseline.
        """
        if not self._baseline:
            # No baseline yet — return raw values normalized to sum
            total = powers.alpha + powers.beta + powers.theta + powers.gamma + powers.delta + EPS
            return {
                "alpha": powers.alpha / total,
                "beta": powers.beta / total,
                "theta": powers.theta / total,
                "gamma": powers.gamma / total,
                "delta": powers.delta / total,
            }

        return {
            band: getattr(powers, band) / max(self._baseline[band], EPS)
            for band in ("alpha", "beta", "theta", "gamma", "delta")
        }


class CognitiveStateClassifier:
    """
    Classifies cognitive state from normalized band powers.

    Heuristics:
        focus_score   = relative_beta / max(relative_theta, eps)
        cognitive_load = relative_beta + relative_gamma

        OVERLOADED  → cognitive_load > LOAD_HIGH_THRESHOLD
        FOCUSED     → focus_score > FOCUS_HIGH_THRESHOLD (and not overloaded)
        DISENGAGED  → focus_score < FOCUS_LOW_THRESHOLD (and not overloaded)
        FOCUSED     → otherwise (moderate engagement)
    """

    def __init__(self) -> None:
        self.calibrator = BaselineCalibrator()

    def classify(self, powers: BandPowers) -> ClassificationResult:
        """Classify band powers into a cognitive state."""
        normalized = self.calibrator.normalize(powers)

        rel_beta = normalized["beta"]
        rel_theta = normalized["theta"]
        rel_gamma = normalized["gamma"]
        rel_alpha = normalized["alpha"]

        focus_score = rel_beta / max(rel_theta, EPS)
        cognitive_load = rel_beta + rel_gamma

        has_baseline = self.calibrator.is_ready

        # Classification rules
        if cognitive_load > LOAD_HIGH_THRESHOLD:
            state = "OVERLOADED"
            # Confidence increases with how far above threshold
            confidence = min(1.0, 0.6 + (cognitive_load - LOAD_HIGH_THRESHOLD) * 0.5)

        elif focus_score > FOCUS_HIGH_THRESHOLD:
            state = "FOCUSED"
            confidence = min(1.0, 0.6 + (focus_score - FOCUS_HIGH_THRESHOLD) * 0.3)

        elif focus_score < FOCUS_LOW_THRESHOLD:
            state = "DISENGAGED"
            confidence = min(1.0, 0.6 + (FOCUS_LOW_THRESHOLD - focus_score) * 0.5)

        else:
            # Moderate engagement — treat as focused with lower confidence
            state = "FOCUSED"
            confidence = 0.55

        # Lower confidence if no baseline yet
        if not has_baseline:
            confidence *= 0.7

        return ClassificationResult(
            state=state,
            confidence=round(confidence, 3),
            focus_score=round(focus_score, 4),
            cognitive_load=round(cognitive_load, 4),
            relative_to_baseline=has_baseline,
        )
