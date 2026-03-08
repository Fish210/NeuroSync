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
from pathlib import Path

from eeg.processor import BandPowers

logger = logging.getLogger(__name__)

# ── Threshold constants (tune via env vars for demo calibration) ──────────
# focus_score = beta / max(theta, eps)
# Values relative to baseline: 1.0 = same as baseline, 2.0 = double baseline
FOCUS_HIGH_THRESHOLD = float(os.getenv("FOCUS_HIGH_THRESHOLD", "1.4"))
FOCUS_LOW_THRESHOLD = float(os.getenv("FOCUS_LOW_THRESHOLD", "0.7"))

# overload_score = (rel_beta + rel_gamma) / rel_alpha
#
# Alpha suppression is the most reliable EEG marker of cognitive overload:
#   - High beta + gamma indicates active processing / arousal
#   - Simultaneously suppressed alpha indicates inability to relax → overload
#   - Dividing by rel_alpha makes the score invariant to absolute power scale
#
# Baseline calibration: at rest, all rel values = 1.0 → score = 2.0/1.0 = 2.0
# Threshold of 3.5 fires when load rises ~75% above the neutral 2.0 baseline.
# Without personal baseline, apply a more conservative 1.5× multiplier (5.25)
# to reduce false positives from inter-individual alpha variability.
OVERLOAD_RATIO_THRESHOLD = float(os.getenv("OVERLOAD_RATIO_THRESHOLD", "3.5"))

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
    Classifies cognitive state from band powers.

    If config/backend/classifier.joblib exists (trained via scripts/training/train_gui.py),
    uses the pretrained SVM. Otherwise falls back to heuristic band power ratios.
    """

    _MODEL_PATH = Path(__file__).parent.parent.parent.parent / "config" / "backend" / "classifier.joblib"
    _BACKUP_DIR = Path(__file__).parent.parent.parent.parent / "config" / "backend" / "backups"

    def __init__(self) -> None:
        self.calibrator = BaselineCalibrator()
        self._pipeline = None
        self._classes: list[str] = []
        self._load_pretrained()

    def _load_pretrained(self) -> None:
        """
        Try to load the trained SVM model. Checks:
          1. config/backend/classifier.joblib  (primary)
          2. config/backend/backups/*.joblib   (newest first, auto-fallback)
        Silently falls back to heuristics if nothing found.
        """
        import joblib

        candidates: list[Path] = [self._MODEL_PATH]
        if self._BACKUP_DIR.exists():
            candidates.extend(sorted(self._BACKUP_DIR.glob("*.joblib"), reverse=True))

        for path in candidates:
            try:
                data = joblib.load(path)
                self._pipeline = data["pipeline"]
                self._classes = data["classes"]
                logger.info(
                    "Pretrained EEG classifier loaded from %s (classes: %s)",
                    path,
                    self._classes,
                )
                return
            except FileNotFoundError:
                continue
            except Exception as exc:
                logger.warning("Failed to load %s: %s — trying next", path, exc)

        logger.info("No pretrained classifier found — using heuristics")

    @property
    def using_pretrained(self) -> bool:
        return self._pipeline is not None

    def classify(self, powers: BandPowers) -> ClassificationResult:
        """Classify band powers into a cognitive state."""
        if self._pipeline is not None:
            return self._classify_pretrained(powers)
        return self._classify_heuristic(powers)

    def _classify_pretrained(self, powers: BandPowers) -> ClassificationResult:
        """
        Use SVM for FOCUSED/DISENGAGED classification.
        OVERLOADED is not in the SVM's training classes, so a heuristic gate
        runs first: if the alpha-normalized overload score exceeds the threshold,
        return OVERLOADED immediately without invoking the SVM.
        """
        import numpy as np
        EPS_LOCAL = 1e-10
        d, t, a, b, g = (
            powers.delta, powers.theta, powers.alpha, powers.beta, powers.gamma
        )

        focus_score = b / max(t, EPS_LOCAL)
        cognitive_load = b + g

        # ── OVERLOADED gate ──────────────────────────────────────────────────
        # Compute alpha-normalized overload score from relative (baseline-aware)
        # band powers. More conservative threshold when baseline is not yet
        # established to reduce false positives from individual alpha variation.
        normalized = self.calibrator.normalize(powers)
        overload_score = (
            (normalized["beta"] + normalized["gamma"]) / max(normalized["alpha"], EPS_LOCAL)
        )
        has_baseline = self.calibrator.is_ready
        overload_threshold = OVERLOAD_RATIO_THRESHOLD if has_baseline else OVERLOAD_RATIO_THRESHOLD * 1.5

        if overload_score > overload_threshold:
            confidence = min(1.0, 0.65 + (overload_score - overload_threshold) * 0.05)
            if not has_baseline:
                confidence *= 0.7
            return ClassificationResult(
                state="OVERLOADED",
                confidence=round(confidence, 3),
                focus_score=round(focus_score, 4),
                cognitive_load=round(cognitive_load, 4),
                relative_to_baseline=has_baseline,
            )
        # ────────────────────────────────────────────────────────────────────

        features = np.array([
            d, t, a, b, g,
            b / max(t, EPS_LOCAL),
            b / max(a, EPS_LOCAL),
            (b + g) / max(a + t, EPS_LOCAL),
            t / max(a, EPS_LOCAL),
        ], dtype=np.float32)

        proba = self._pipeline.predict_proba(features.reshape(1, -1))[0]
        idx = int(np.argmax(proba))
        state = self._classes[idx]
        confidence = float(proba[idx])

        return ClassificationResult(
            state=state,
            confidence=round(confidence, 3),
            focus_score=round(focus_score, 4),
            cognitive_load=round(cognitive_load, 4),
            relative_to_baseline=False,
        )

    def _classify_heuristic(self, powers: BandPowers) -> ClassificationResult:
        """
        Heuristic classifier with alpha-normalized OVERLOADED detection.

        OVERLOADED detection uses the ratio:
            overload_score = (rel_beta + rel_gamma) / rel_alpha

        Alpha suppression is the primary EEG marker of cognitive overload —
        dividing by rel_alpha amplifies the signal when alpha is suppressed
        while beta+gamma are elevated. At neutral baseline all rel values
        equal 1.0, giving a score of 2.0 — safely below the 3.5 threshold.
        Without a personal baseline a 1.5× conservative multiplier is applied.
        """
        normalized = self.calibrator.normalize(powers)

        rel_beta = normalized["beta"]
        rel_theta = normalized["theta"]
        rel_gamma = normalized["gamma"]
        rel_alpha = normalized["alpha"]

        focus_score = rel_beta / max(rel_theta, EPS)
        cognitive_load = rel_beta + rel_gamma

        # Alpha-normalized overload score — invariant to absolute power scale
        overload_score = cognitive_load / max(rel_alpha, EPS)

        has_baseline = self.calibrator.is_ready
        overload_threshold = OVERLOAD_RATIO_THRESHOLD if has_baseline else OVERLOAD_RATIO_THRESHOLD * 1.5

        if overload_score > overload_threshold:
            state = "OVERLOADED"
            confidence = min(1.0, 0.65 + (overload_score - overload_threshold) * 0.05)

        elif focus_score > FOCUS_HIGH_THRESHOLD:
            state = "FOCUSED"
            confidence = min(1.0, 0.6 + (focus_score - FOCUS_HIGH_THRESHOLD) * 0.3)

        elif focus_score < FOCUS_LOW_THRESHOLD:
            state = "DISENGAGED"
            confidence = min(1.0, 0.6 + (FOCUS_LOW_THRESHOLD - focus_score) * 0.5)

        else:
            state = "FOCUSED"
            confidence = 0.55

        if not has_baseline:
            confidence *= 0.7

        return ClassificationResult(
            state=state,
            confidence=round(confidence, 3),
            focus_score=round(focus_score, 4),
            cognitive_load=round(cognitive_load, 4),
            relative_to_baseline=has_baseline,
        )
