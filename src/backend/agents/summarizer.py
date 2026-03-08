"""
Session narrative summarizer.

Generates a 2-3 sentence human-readable summary of a tutoring session.
Falls back to a template string if FEATHERLESS_API_KEY is not set.

Called from: api/routes.py POST /stop-session
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

FEATHERLESS_API_KEY = os.getenv("FEATHERLESS_API_KEY", "")
FEATHERLESS_BASE_URL = os.getenv("FEATHERLESS_BASE_URL", "https://api.featherless.ai/v1")
SPEAKER_MODEL = os.getenv("SPEAKER_MODEL", "Qwen/Qwen2.5-7B-Instruct")


def _template_narrative(
    topic: str,
    duration_seconds: int,
    state_breakdown: dict[str, int],
    topics_covered: list[dict],
) -> str:
    """Generate a template narrative without an API call."""
    minutes = duration_seconds // 60
    focused = state_breakdown.get("FOCUSED", 0)
    overloaded = state_breakdown.get("OVERLOADED", 0)
    total = max(duration_seconds, 1)

    focused_pct = int(focused / total * 100)
    overloaded_pct = int(overloaded / total * 100)

    strong = [t["title"] for t in topics_covered if t.get("comprehension") == "strong"]
    needs_review = [t["title"] for t in topics_covered if t.get("comprehension") == "needs_review"]

    parts = [
        f"The student studied {topic} for {minutes} minute{'s' if minutes != 1 else ''}.",
        f"They were focused {focused_pct}% of the time and showed signs of overload {overloaded_pct}% of the time.",
    ]

    if strong:
        parts.append(f"Strong understanding of: {', '.join(strong)}.")
    if needs_review:
        parts.append(f"Needs further review: {', '.join(needs_review)}.")

    return " ".join(parts)


async def generate_narrative(
    topic: str,
    duration_seconds: int,
    state_breakdown: dict[str, int],
    topics_covered: list[dict],
) -> str:
    """
    Generate a concise session narrative.
    Returns template string if API unavailable.
    """
    if not FEATHERLESS_API_KEY:
        return _template_narrative(topic, duration_seconds, state_breakdown, topics_covered)

    try:
        from openai import AsyncOpenAI

        minutes = duration_seconds // 60
        focused_pct = int(state_breakdown.get("FOCUSED", 0) / max(duration_seconds, 1) * 100)
        overloaded_pct = int(state_breakdown.get("OVERLOADED", 0) / max(duration_seconds, 1) * 100)

        topic_lines = "\n".join(
            f"- {t['title']}: {t.get('comprehension', 'unknown')} comprehension"
            for t in topics_covered
        )

        prompt = (
            f"Write a 2-3 sentence summary of this tutoring session.\n\n"
            f"Topic: {topic}\n"
            f"Duration: {minutes} minutes\n"
            f"Student was focused {focused_pct}% of the time, overloaded {overloaded_pct}%.\n"
            f"Topics covered:\n{topic_lines}\n\n"
            f"Write a brief, encouraging summary for the student. Plain text only, no bullet points."
        )

        client = AsyncOpenAI(
            api_key=FEATHERLESS_API_KEY,
            base_url=FEATHERLESS_BASE_URL,
        )

        response = await client.chat.completions.create(
            model=SPEAKER_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            max_tokens=120,
            timeout=8.0,
        )

        narrative = (response.choices[0].message.content or "").strip()
        logger.info("Session narrative generated (%d chars)", len(narrative))
        return narrative

    except Exception as exc:
        logger.warning("Narrative generation failed: %s — using template", exc)
        return _template_narrative(topic, duration_seconds, state_breakdown, topics_covered)
