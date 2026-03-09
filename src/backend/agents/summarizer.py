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
SUMMARIZER_MODEL = os.getenv("SUMMARIZER_MODEL", "meta-llama/Llama-3.3-70B-Instruct")


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

        system_prompt = (
            "You are a warm, encouraging learning coach writing a brief post-session summary "
            "for a student. Be specific about what they did well and honest about areas to revisit. "
            "Write in second person ('You spent...', 'You showed...'). "
            "Plain text only — no bullet points, no markdown. 2-3 sentences maximum."
        )

        user_prompt = (
            f"Write a post-session summary for a student who just finished studying '{topic}'.\n\n"
            f"Session stats:\n"
            f"- Duration: {minutes} minutes\n"
            f"- Focused: {focused_pct}% of the time\n"
            f"- Overloaded: {overloaded_pct}% of the time\n"
            f"- Disengaged: {100 - focused_pct - overloaded_pct}% of the time\n"
        )
        if topics_covered:
            user_prompt += "\nTopics and comprehension:\n" + "\n".join(
                f"- {t['title']}: {t.get('comprehension', 'unknown').replace('_', ' ')}"
                for t in topics_covered
            )

        client = AsyncOpenAI(
            api_key=FEATHERLESS_API_KEY,
            base_url=FEATHERLESS_BASE_URL,
        )

        response = await client.chat.completions.create(
            model=SUMMARIZER_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.5,
            max_tokens=150,
            timeout=15.0,
        )

        narrative = (response.choices[0].message.content or "").strip()
        logger.info("Session narrative generated (%d chars)", len(narrative))
        return narrative

    except Exception as exc:
        logger.warning("Narrative generation failed: %s — using template", exc)
        return _template_narrative(topic, duration_seconds, state_breakdown, topics_covered)
