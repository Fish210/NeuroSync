"""Tests for session narrative summarizer."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src" / "backend"))

from agents.summarizer import _template_narrative


def test_template_narrative_contains_topic():
    result = _template_narrative(
        topic="derivatives",
        duration_seconds=600,
        state_breakdown={"FOCUSED": 400, "OVERLOADED": 150, "DISENGAGED": 50},
        topics_covered=[
            {"title": "Limits", "comprehension": "strong"},
            {"title": "Power rule", "comprehension": "needs_review"},
        ],
    )
    assert "derivatives" in result
    assert "10 minute" in result


def test_template_narrative_no_topics():
    result = _template_narrative(
        topic="calculus",
        duration_seconds=120,
        state_breakdown={"FOCUSED": 120},
        topics_covered=[],
    )
    assert "calculus" in result
    assert len(result) > 20


def test_template_narrative_strong_comprehension():
    result = _template_narrative(
        topic="physics",
        duration_seconds=300,
        state_breakdown={"FOCUSED": 300},
        topics_covered=[{"title": "Newton's laws", "comprehension": "strong"}],
    )
    assert "Newton" in result
