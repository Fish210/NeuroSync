"""
Cognitive state per-topic tracker.

Records (topic, timestamp, cognitive_state) tuples throughout the session.
Used to generate the post-session summary: per-topic comprehension inference.

Comprehension mapping:
    FOCUSED dominant   → "strong"
    DISENGAGED dominant → "moderate"
    OVERLOADED dominant → "needs_review"
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import DefaultDict
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class TopicStateEntry:
    topic_id: str
    topic_title: str
    state: str
    timestamp: float = field(default_factory=time.time)


class TopicStateTracker:
    """
    Tracks cognitive state per topic throughout a session.

    Usage:
        tracker = TopicStateTracker(lesson_plan)
        tracker.record("FOCUSED")   # records for current topic
        tracker.advance_topic()     # move to next block
        summary = tracker.compute_summary()
    """

    def __init__(self, lesson_plan: dict) -> None:
        self._blocks: list[dict] = lesson_plan.get("blocks", [])
        self._current_idx: int = 0
        self._entries: list[TopicStateEntry] = []
        self._session_start: float = time.time()

        logger.info(
            "TopicStateTracker initialized with %d blocks", len(self._blocks)
        )

    @property
    def current_block(self) -> dict | None:
        if 0 <= self._current_idx < len(self._blocks):
            return self._blocks[self._current_idx]
        return None

    def record(self, state: str) -> None:
        """Record the current cognitive state for the active topic."""
        block = self.current_block
        if not block:
            return
        self._entries.append(TopicStateEntry(
            topic_id=block["id"],
            topic_title=block["title"],
            state=state,
        ))

    def advance_topic(self) -> dict | None:
        """Move to the next lesson block. Returns new block or None."""
        if self._current_idx < len(self._blocks) - 1:
            self._current_idx += 1
            block = self._blocks[self._current_idx]
            logger.info("Advanced to topic: %s", block["title"])
            return block
        logger.info("Already at last topic block")
        return None

    def compute_summary(
        self,
        state_log: list[tuple[float, str]],
    ) -> dict:
        """
        Compute post-session summary from tracked data and state log.

        Args:
            state_log: list of (timestamp, state) tuples from the session

        Returns:
            dict matching SessionSummary schema
        """
        duration = int(time.time() - self._session_start)

        # State breakdown: seconds in each state
        state_breakdown: DefaultDict[str, int] = defaultdict(int)
        for i, (ts, state) in enumerate(state_log):
            next_ts = state_log[i + 1][0] if i + 1 < len(state_log) else time.time()
            state_breakdown[state] += int(next_ts - ts)

        # Per-topic analysis
        topics_covered: list[dict] = []
        seen_topics: set[str] = set()

        for block in self._blocks:
            block_id = block["id"]
            block_entries = [e for e in self._entries if e.topic_id == block_id]

            if not block_entries:
                continue

            seen_topics.add(block_id)
            duration_secs = len(block_entries)  # 1 entry ≈ 1 processing cycle (~1s)

            # Count dominant state
            state_counts: DefaultDict[str, int] = defaultdict(int)
            for entry in block_entries:
                state_counts[entry.state] += 1

            dominant = max(state_counts, key=state_counts.get)

            comprehension_map = {
                "FOCUSED": "strong",
                "DISENGAGED": "moderate",
                "OVERLOADED": "needs_review",
            }

            topics_covered.append({
                "title": block["title"],
                "duration_seconds": duration_secs,
                "dominant_state": dominant,
                "comprehension": comprehension_map.get(dominant, "moderate"),
            })

        return {
            "duration_seconds": duration,
            "state_breakdown": dict(state_breakdown),
            "topics": topics_covered,
        }
