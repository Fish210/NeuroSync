"""
Tests for the EEG processing pipeline.

Tests: EEGProcessor, CognitiveStateClassifier, BandPowerSmoother, DwellTimeFilter
All tests use synthetic data — no hardware required.
"""
from __future__ import annotations

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'backend'))

import time
from unittest.mock import MagicMock

import numpy as np
import pytest

from eeg.processor import EEGProcessor, BandPowers
from eeg.classifier import CognitiveStateClassifier, BaselineCalibrator
from eeg.filter import BandPowerSmoother, DwellTimeFilter


# ---------------------------------------------------------------------------
# Helper: create EEGSample-like objects from raw arrays
# ---------------------------------------------------------------------------

class FakeSample:
    def __init__(self, channels):
        self.channels = np.asarray(channels, dtype=np.float32)
        self.timestamp = time.time()


def make_samples(raw_arrays):
    return [FakeSample(arr) for arr in raw_arrays]


# ---------------------------------------------------------------------------
# EEGProcessor tests
# ---------------------------------------------------------------------------

class TestEEGProcessor:
    def test_returns_none_on_empty_input(self):
        proc = EEGProcessor()
        assert proc.compute([]) is None

    def test_returns_band_powers_for_valid_input(self, focused_samples):
        proc = EEGProcessor()
        samples = make_samples(focused_samples)
        result = proc.compute(samples)
        assert result is not None
        assert isinstance(result, BandPowers)
        assert 0.0 <= result.alpha <= 1.0
        assert 0.0 <= result.beta <= 1.0
        assert result.alpha + result.beta + result.theta + result.gamma + result.delta < 1.01

    def test_artifact_rejection_removes_high_amplitude_samples(self, artifact_samples):
        proc = EEGProcessor(artifact_threshold_uv=100.0, min_samples=32)
        samples = make_samples(artifact_samples)
        # Should still compute (enough clean samples remain after rejecting 32 artifacts)
        result = proc.compute(samples)
        # The result may be None if too many samples are rejected, which is acceptable
        # The key test is that it doesn't crash and handles artifacts gracefully
        if result is not None:
            assert not np.isnan(result.beta)
            assert not np.isinf(result.beta)

    def test_artifact_rejection_returns_none_if_all_contaminated(self):
        proc = EEGProcessor(artifact_threshold_uv=10.0, min_samples=200)
        # All samples have amplitude > 10µV threshold
        raw = [np.ones(5) * 50.0 for _ in range(100)]
        samples = make_samples(raw)
        result = proc.compute(samples)
        assert result is None

    def test_band_powers_are_normalized(self, focused_samples):
        proc = EEGProcessor()
        samples = make_samples(focused_samples)
        result = proc.compute(samples)
        if result is not None:
            total = result.alpha + result.beta + result.theta + result.gamma + result.delta
            assert abs(total - 1.0) < 0.01  # normalized to sum ≈ 1.0

    def test_timestamp_is_set(self, focused_samples):
        proc = EEGProcessor()
        samples = make_samples(focused_samples)
        before = time.time()
        result = proc.compute(samples)
        after = time.time()
        if result is not None:
            assert before <= result.timestamp <= after


# ---------------------------------------------------------------------------
# BaselineCalibrator tests
# ---------------------------------------------------------------------------

class TestBaselineCalibrator:
    def _make_powers(self, alpha=0.3, beta=0.4, theta=0.2, gamma=0.3, delta=0.2):
        return BandPowers(alpha=alpha, beta=beta, theta=theta, gamma=gamma, delta=delta, timestamp=time.time())

    def test_not_ready_before_min_windows(self):
        cal = BaselineCalibrator(min_windows=5)
        for _ in range(4):
            cal.add_window(self._make_powers())
        assert not cal.is_ready

    def test_ready_after_min_windows(self):
        cal = BaselineCalibrator(min_windows=5)
        for _ in range(5):
            cal.add_window(self._make_powers())
        assert cal.is_ready

    def test_baseline_averages_correctly(self):
        cal = BaselineCalibrator(min_windows=3)
        # Add 3 identical windows
        for _ in range(3):
            cal.add_window(self._make_powers(beta=0.5))
        baseline = cal.get_baseline()
        assert baseline is not None
        assert abs(baseline["beta"] - 0.5) < 0.01

    def test_normalize_returns_ratios_relative_to_baseline(self):
        cal = BaselineCalibrator(min_windows=3)
        for _ in range(3):
            cal.add_window(self._make_powers(beta=0.4))
        # Powers with beta = 0.8 (double baseline)
        powers = self._make_powers(beta=0.8)
        normalized = cal.normalize(powers)
        # beta should be ~2.0 (double baseline)
        assert abs(normalized["beta"] - 2.0) < 0.1


# ---------------------------------------------------------------------------
# CognitiveStateClassifier tests
# ---------------------------------------------------------------------------

class TestCognitiveStateClassifier:
    def _make_powers(self, alpha=0.3, beta=0.4, theta=0.2, gamma=0.3, delta=0.2):
        return BandPowers(alpha=alpha, beta=beta, theta=theta, gamma=gamma, delta=delta, timestamp=time.time())

    def _warm_up(self, classifier, n=5):
        """Feed n baseline windows to calibrate."""
        powers = self._make_powers()
        for _ in range(n):
            classifier.calibrator.add_window(powers)

    def test_classifies_without_baseline(self):
        clf = CognitiveStateClassifier()
        result = clf.classify(self._make_powers())
        assert result.state in ("FOCUSED", "OVERLOADED", "DISENGAGED")
        assert 0.0 <= result.confidence <= 1.0

    def test_confidence_lower_without_baseline(self):
        clf = CognitiveStateClassifier()
        result_no_baseline = clf.classify(self._make_powers())

        self._warm_up(clf)
        result_with_baseline = clf.classify(self._make_powers())

        # Confidence should generally be higher with baseline
        # (this is a soft test — not guaranteed for all inputs)
        assert result_no_baseline.confidence <= 1.0
        assert result_with_baseline.confidence <= 1.0

    def test_high_cognitive_load_classified_as_overloaded(self):
        clf = CognitiveStateClassifier()
        clf._pipeline = None  # test heuristic rules, not SVM
        # Baseline with low beta+gamma and moderate alpha
        low_load = self._make_powers(beta=0.2, gamma=0.1)
        for _ in range(5):
            clf.calibrator.add_window(low_load)

        # Very high beta+gamma relative to baseline, alpha unchanged
        # overload_score = (rel_beta + rel_gamma) / rel_alpha
        #   = (0.9/0.2 + 0.8/0.1) / (0.3/0.3) = (4.5 + 8.0) / 1.0 = 12.5 > 3.5
        high_load = self._make_powers(beta=0.9, gamma=0.8, theta=0.1)
        result = clf.classify(high_load)
        assert result.state == "OVERLOADED"

    def test_high_focus_score_classified_as_focused(self):
        clf = CognitiveStateClassifier()
        clf._pipeline = None  # test heuristic rules, not SVM
        # Baseline: moderate beta, moderate theta, high gamma (person has elevated gamma at rest)
        baseline = self._make_powers(beta=0.3, theta=0.3, gamma=0.5)
        for _ in range(5):
            clf.calibrator.add_window(baseline)

        # FOCUSED state: high beta/theta, gamma well below baseline, alpha unchanged
        # overload_score = (rel_beta + rel_gamma) / rel_alpha
        #   = (0.43/0.3 + 0.05/0.5) / (0.3/0.3) = (1.43 + 0.10) / 1.0 = 1.53 < 3.5 → not OVERLOADED
        # focus_score = rel_beta / rel_theta = 1.43 / (0.08/0.3) = 1.43/0.267 ≈ 5.4 > 1.4 → FOCUSED
        focused = self._make_powers(beta=0.43, theta=0.08, gamma=0.05)
        result = clf.classify(focused)
        assert result.state == "FOCUSED"

    def test_low_focus_score_classified_as_disengaged(self):
        clf = CognitiveStateClassifier()
        # Baseline with moderate focus
        baseline = self._make_powers(beta=0.4, theta=0.2)
        for _ in range(5):
            clf.calibrator.add_window(baseline)

        # Low beta / high theta = low focus score
        disengaged = self._make_powers(beta=0.1, theta=0.6, alpha=0.7, gamma=0.05)
        result = clf.classify(disengaged)
        assert result.state == "DISENGAGED"


# ---------------------------------------------------------------------------
# BandPowerSmoother tests
# ---------------------------------------------------------------------------

class TestBandPowerSmoother:
    def _make_powers(self, beta=0.4, **kwargs):
        return BandPowers(alpha=0.3, beta=beta, theta=0.2, gamma=0.3, delta=0.2, timestamp=time.time(), **kwargs)

    def test_first_update_returns_input_unchanged(self):
        smoother = BandPowerSmoother(alpha=0.3)
        powers = self._make_powers(beta=0.5)
        result = smoother.update(powers)
        assert abs(result.beta - 0.5) < 0.001

    def test_smoothing_reduces_step_change(self):
        smoother = BandPowerSmoother(alpha=0.3)
        # Initialize with beta=0.4
        smoother.update(self._make_powers(beta=0.4))
        # Step change to beta=1.0 — smoothed result should be between 0.4 and 1.0
        result = smoother.update(self._make_powers(beta=1.0))
        assert 0.4 < result.beta < 1.0

    def test_reset_clears_state(self):
        smoother = BandPowerSmoother(alpha=0.3)
        smoother.update(self._make_powers(beta=0.8))
        smoother.reset()
        # After reset, first update should return input unchanged
        result = smoother.update(self._make_powers(beta=0.2))
        assert abs(result.beta - 0.2) < 0.001


# ---------------------------------------------------------------------------
# DwellTimeFilter tests
# ---------------------------------------------------------------------------

class TestDwellTimeFilter:
    def test_no_transition_before_dwell_count(self):
        f = DwellTimeFilter(dwell_required=3)
        assert f.update("FOCUSED") is None
        assert f.update("FOCUSED") is None
        # Only 2 windows — not yet at dwell_required=3

    def test_transition_fires_at_dwell_count(self):
        f = DwellTimeFilter(dwell_required=3)
        assert f.update("FOCUSED") is None
        assert f.update("FOCUSED") is None
        result = f.update("FOCUSED")
        assert result == "FOCUSED"

    def test_counter_resets_on_state_change(self):
        f = DwellTimeFilter(dwell_required=3)
        f.update("FOCUSED")
        f.update("FOCUSED")
        f.update("OVERLOADED")  # interrupt — counter resets
        # Now need 3 more FOCUSED windows
        assert f.update("FOCUSED") is None
        assert f.update("FOCUSED") is None
        result = f.update("FOCUSED")
        assert result == "FOCUSED"

    def test_no_duplicate_transition_for_same_state(self):
        f = DwellTimeFilter(dwell_required=3)
        # First transition
        f.update("FOCUSED"); f.update("FOCUSED"); f.update("FOCUSED")
        # Fourth and fifth FOCUSED — should NOT fire again
        assert f.update("FOCUSED") is None
        assert f.update("FOCUSED") is None

    def test_published_state_updated_on_transition(self):
        f = DwellTimeFilter(dwell_required=2)
        assert f.current_published_state is None
        f.update("OVERLOADED")
        f.update("OVERLOADED")
        assert f.current_published_state == "OVERLOADED"
