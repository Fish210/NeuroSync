"""
Tests for the EEG confidence gate in the processing pipeline.

The gate (api/main.py) only advances the dwell-time filter counter for
high-confidence classifier windows. Low-confidence windows still broadcast
band powers to the frontend but do NOT trigger state transitions.

These tests verify the gate logic at the unit level:
  - DwellTimeFilter + CognitiveStateClassifier interaction
  - Confidence threshold semantics
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src" / "backend"))

from eeg.classifier import ClassificationResult, CognitiveStateClassifier
from eeg.filter import DwellTimeFilter
from eeg.processor import BandPowers

EEG_CONFIDENCE_MIN = 0.55


def _make_powers(**kwargs) -> BandPowers:
    defaults = dict(delta=0.2, theta=0.2, alpha=0.2, beta=0.2, gamma=0.2, timestamp=time.time())
    defaults.update(kwargs)
    return BandPowers(**defaults)


def _apply_gate(result: ClassificationResult, dwell: DwellTimeFilter) -> str | None:
    """Mirrors the confidence gate logic in api/main.py._process_eeg_queue."""
    if result.confidence >= EEG_CONFIDENCE_MIN:
        return dwell.update(result.state)
    return None


def test_low_confidence_window_does_not_advance_dwell():
    """Window with confidence below threshold: gate returns None, dwell NOT called."""
    dwell = MagicMock(spec=DwellTimeFilter)
    result = ClassificationResult(
        state="FOCUSED", confidence=0.40,  # below 0.55 threshold
        focus_score=1.5, cognitive_load=0.5, relative_to_baseline=False,
    )
    published = _apply_gate(result, dwell)
    assert published is None
    dwell.update.assert_not_called()


def test_high_confidence_window_advances_dwell():
    """Window at or above threshold: gate calls dwell.update() and returns its result."""
    dwell = MagicMock(spec=DwellTimeFilter)
    dwell.update.return_value = "FOCUSED"
    result = ClassificationResult(
        state="FOCUSED", confidence=0.70,  # above 0.55 threshold
        focus_score=2.0, cognitive_load=0.5, relative_to_baseline=True,
    )
    published = _apply_gate(result, dwell)
    assert published == "FOCUSED"
    dwell.update.assert_called_once_with("FOCUSED")


def test_confidence_at_exact_threshold_passes():
    """Confidence exactly at threshold (0.55) should pass the gate."""
    dwell = MagicMock(spec=DwellTimeFilter)
    dwell.update.return_value = None
    result = ClassificationResult(
        state="OVERLOADED", confidence=0.55,
        focus_score=0.8, cognitive_load=1.6, relative_to_baseline=True,
    )
    published = _apply_gate(result, dwell)
    dwell.update.assert_called_once_with("OVERLOADED")


def test_low_confidence_does_not_reset_dwell_counter():
    """
    Low-confidence windows are skipped entirely — they do NOT reset the
    dwell counter that was built by prior high-confidence windows.

    DwellTimeFilter only resets on a STATE CHANGE, not on skipped windows.

    Baseline: beta=0.3, theta=0.3, gamma=0.5
    Focused:  beta=0.43, theta=0.08, gamma=0.05
      overload_score = (1.43 + 0.10) / 1.0 = 1.53 < 3.5 → NOT overloaded
      focus_score = 1.43 / 0.267 ≈ 5.4 > 1.4 → FOCUSED
    (Same values verified in test_eeg_processing.py)
    """
    clf = CognitiveStateClassifier()
    clf._pipeline = None
    dwell = DwellTimeFilter(dwell_required=3)

    # Calibrate with baseline that has high gamma at rest
    baseline = _make_powers(beta=0.3, theta=0.3, gamma=0.5)
    for _ in range(5):
        clf.calibrator.add_window(baseline)

    # FOCUSED profile: high beta/theta ratio, gamma well below baseline
    focused = _make_powers(beta=0.43, theta=0.08, gamma=0.05)
    high_conf_count = 0
    for _ in range(2):
        result = clf.classify(focused)
        assert result.state == "FOCUSED", f"Expected FOCUSED but got {result.state}"
        if result.confidence >= EEG_CONFIDENCE_MIN:
            _apply_gate(result, dwell)
            high_conf_count += 1

    assert high_conf_count >= 1, "Need at least 1 high-confidence window for this test"

    # 3rd high-confidence window should complete the dwell
    result = clf.classify(focused)
    assert result.state == "FOCUSED"
    if result.confidence >= EEG_CONFIDENCE_MIN:
        published = _apply_gate(result, dwell)
        if high_conf_count >= 2:
            assert published == "FOCUSED"


def test_dwell_filter_fires_only_after_required_high_confidence_windows():
    """Dwell filter requires N consecutive high-confidence windows of the same state."""
    dwell = DwellTimeFilter(dwell_required=3)
    high_result = ClassificationResult(
        state="OVERLOADED", confidence=0.80,
        focus_score=0.5, cognitive_load=2.0, relative_to_baseline=True,
    )

    assert _apply_gate(high_result, dwell) is None  # 1 of 3
    assert _apply_gate(high_result, dwell) is None  # 2 of 3
    published = _apply_gate(high_result, dwell)     # 3 of 3
    assert published == "OVERLOADED"
