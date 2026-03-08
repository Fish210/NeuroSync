"""Unit tests for training feature extraction."""
import sys
from pathlib import Path
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "training"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src" / "backend"))

from eeg.ingestion import EEGSample
from train import extract_features, build_dataset, EPS


def _make_samples(n: int = 600, amplitude: float = 10.0) -> list[EEGSample]:
    """Generate synthetic EEG samples (below artifact threshold)."""
    rng = np.random.default_rng(42)
    return [
        EEGSample(
            channels=rng.normal(0, amplitude, size=(5,)).astype(np.float32),
            timestamp=float(i) / 256.0,
        )
        for i in range(n)
    ]


def test_extract_features_returns_9_values():
    samples = _make_samples(600)
    feat = extract_features(samples[:512])
    assert feat is not None
    assert feat.shape == (9,)


def test_extract_features_no_nans():
    samples = _make_samples(600)
    feat = extract_features(samples[:512])
    assert feat is not None
    assert not np.any(np.isnan(feat))


def test_extract_features_too_few_samples():
    samples = _make_samples(10)
    feat = extract_features(samples)
    assert feat is None


def test_build_dataset_shape():
    phase_data = [
        ("FOCUSED", _make_samples(1000)),
        ("OVERLOADED", _make_samples(1000)),
        ("DISENGAGED", _make_samples(1000)),
    ]
    X, y, classes = build_dataset(phase_data)
    assert X.shape[1] == 9
    assert len(X) == len(y)
    assert set(classes) == {"FOCUSED", "OVERLOADED", "DISENGAGED"}
    assert len(classes) == 3


def test_build_dataset_all_classes_represented():
    phase_data = [
        ("FOCUSED", _make_samples(800)),
        ("OVERLOADED", _make_samples(800)),
        ("DISENGAGED", _make_samples(800)),
    ]
    X, y, classes = build_dataset(phase_data)
    for i in range(len(classes)):
        assert (y == i).sum() > 0
