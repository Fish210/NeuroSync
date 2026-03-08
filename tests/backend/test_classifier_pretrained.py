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
    """When no model file exists, classifier uses heuristics."""
    monkeypatch.setattr(
        CognitiveStateClassifier,
        "_MODEL_PATH",
        tmp_path / "nonexistent.joblib",
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
    clf = CognitiveStateClassifier()
    assert clf.using_pretrained is False
