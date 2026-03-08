"""Unit tests for VoiceActivityDetector."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src" / "backend"))

from voice.vad import VoiceActivityDetector


def test_no_barge_in_below_threshold():
    vad = VoiceActivityDetector(threshold=0.6, consecutive=3)
    for _ in range(10):
        assert not vad.update(0.3)


def test_barge_in_after_consecutive_readings():
    vad = VoiceActivityDetector(threshold=0.6, consecutive=3)
    assert not vad.update(0.8)
    assert not vad.update(0.8)
    assert vad.update(0.8)  # 3rd consecutive → True


def test_barge_in_fires_only_once():
    vad = VoiceActivityDetector(threshold=0.6, consecutive=3)
    vad.update(0.8)
    vad.update(0.8)
    assert vad.update(0.8)   # fires
    assert not vad.update(0.8)  # already active, does not fire again
    assert not vad.update(0.8)


def test_resets_after_silence():
    vad = VoiceActivityDetector(threshold=0.6, consecutive=3)
    vad.update(0.8)
    vad.update(0.8)
    assert vad.update(0.8)   # fires
    vad.update(0.1)           # silence — resets
    vad.update(0.8)
    vad.update(0.8)
    assert vad.update(0.8)   # fires again after reset


def test_partial_sequence_does_not_fire():
    vad = VoiceActivityDetector(threshold=0.6, consecutive=3)
    vad.update(0.8)
    vad.update(0.8)
    vad.update(0.1)  # silence breaks run
    vad.update(0.8)
    vad.update(0.8)
    assert not vad.update(0.1)  # only 2 consecutive, no fire
