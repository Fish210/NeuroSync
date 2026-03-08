"""Tests for pretrained model loading and fallback."""
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src" / "backend"))

from eeg.classifier import CognitiveStateClassifier
from eeg.processor import BandPowers


def _make_powers(**kwargs) -> BandPowers:
    defaults = dict(
        delta=0.2, theta=0.2, alpha=0.2, beta=0.2, gamma=0.2,
        timestamp=time.time()
    )
    defaults.update(kwargs)
    return BandPowers(**defaults)


def test_classifier_falls_back_to_heuristics_when_no_model(tmp_path, monkeypatch):
    """When no model file exists (primary or backups), classifier uses heuristics."""
    monkeypatch.setattr(
        CognitiveStateClassifier,
        "_MODEL_PATH",
        tmp_path / "nonexistent.joblib",
    )
    monkeypatch.setattr(
        CognitiveStateClassifier,
        "_BACKUP_DIR",
        tmp_path / "backups",  # empty dir — no backups
    )
    clf = CognitiveStateClassifier()
    assert not clf.using_pretrained


def test_heuristic_classify_returns_valid_state():
    clf = CognitiveStateClassifier()
    clf._pipeline = None  # force heuristic path

    powers = _make_powers(beta=0.5, theta=0.1, gamma=0.3)
    result = clf.classify(powers)
    assert result.state in ("FOCUSED", "OVERLOADED", "DISENGAGED")
    assert 0.0 <= result.confidence <= 1.0


def test_classify_result_has_required_fields():
    clf = CognitiveStateClassifier()
    clf._pipeline = None
    result = clf.classify(_make_powers())
    assert hasattr(result, "state")
    assert hasattr(result, "confidence")
    assert hasattr(result, "focus_score")
    assert hasattr(result, "cognitive_load")
    assert hasattr(result, "relative_to_baseline")


def test_using_pretrained_false_without_model(tmp_path, monkeypatch):
    monkeypatch.setattr(
        CognitiveStateClassifier,
        "_MODEL_PATH",
        tmp_path / "nonexistent.joblib",
    )
    monkeypatch.setattr(
        CognitiveStateClassifier,
        "_BACKUP_DIR",
        tmp_path / "backups",  # empty dir — no backups
    )
    clf = CognitiveStateClassifier()
    assert clf.using_pretrained is False


def test_pretrained_path_detects_overloaded_via_heuristic():
    """
    Even when the SVM is loaded (no OVERLOADED class), the OVERLOADED gate
    in _classify_pretrained should return OVERLOADED when the alpha-normalized
    overload score exceeds OVERLOAD_RATIO_THRESHOLD.

    overload_score = (rel_beta + rel_gamma) / rel_alpha
    Baseline: beta=0.2, gamma=0.1, alpha=0.3
    Overloaded: beta=0.9, gamma=0.8, alpha=0.3
    → rel_beta=4.5, rel_gamma=8.0, rel_alpha=1.0 → score=12.5 > 3.5
    """
    clf = CognitiveStateClassifier()
    if not clf.using_pretrained:
        pytest.skip("No pretrained model available — only meaningful with SVM loaded")

    # Calibrate baseline with low cognitive load
    baseline = _make_powers(beta=0.2, gamma=0.1, alpha=0.3)
    for _ in range(5):
        clf.calibrator.add_window(baseline)

    # Strongly OVERLOADED profile: high beta+gamma, alpha unchanged
    overloaded = _make_powers(beta=0.9, gamma=0.8, theta=0.1, alpha=0.3)
    result = clf.classify(overloaded)
    assert result.state == "OVERLOADED"
    assert result.confidence >= 0.65
