"""
Lesson plan generator.

Calls Featherless 70B model to produce a structured lesson plan for any topic.
Falls back to a minimal hardcoded plan if the API call fails or key is missing.

Called from: api/routes.py POST /start-session
"""
from __future__ import annotations

import json
import logging
import os
import re

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

FEATHERLESS_API_KEY = os.getenv("FEATHERLESS_API_KEY", "")
FEATHERLESS_BASE_URL = os.getenv("FEATHERLESS_BASE_URL", "https://api.featherless.ai/v1")
PLANNER_MODEL = os.getenv("PLANNER_MODEL", "meta-llama/Llama-3.3-70B-Instruct")

_SYSTEM_PROMPT = """You are an expert curriculum designer specializing in adaptive learning. Given a topic a student wants to learn, create a pedagogically sound lesson plan optimized for real-time neuroadaptive delivery — the AI tutor adjusts pacing and depth every few seconds based on EEG cognitive state (FOCUSED / OVERLOADED / DISENGAGED).

Design principles:
- Apply Bloom's Taxonomy: start with recall/comprehension (difficulty 1), build to application/analysis (difficulty 2), end with synthesis/evaluation or practice (difficulty 3)
- Titles must be concrete and specific — NOT generic ("Introduction to X") but specific and evocative ("What a derivative means geometrically: the slope of the tangent line")
- Each block is teachable in 5–10 minutes; natural breakpoints between blocks
- Build incrementally — each block assumes mastery of the prior one
- Last block is always a practice or "check for understanding" exercise

Return ONLY valid JSON — no markdown fences, no explanation, no extra text:
{
  "topic": "<exact topic string>",
  "blocks": [
    {"id": "block-1", "title": "<specific concrete title>", "difficulty": 1},
    {"id": "block-2", "title": "<specific concrete title>", "difficulty": 2},
    {"id": "block-3", "title": "<specific concrete title>", "difficulty": 2},
    {"id": "block-4", "title": "<specific concrete title>", "difficulty": 3}
  ],
  "current_block": "block-1"
}

Hard constraints:
- 4 to 6 blocks total, ascending difficulty
- difficulty is an integer: 1 (foundational), 2 (core), or 3 (advanced/practice)
- "current_block" is always "block-1"
- Return ONLY the raw JSON object — nothing else"""


def _fallback_plan(topic: str) -> dict:
    """Minimal hardcoded plan used when the API is unavailable."""
    return {
        "topic": topic,
        "blocks": [
            {"id": "block-1", "title": f"Introduction to {topic}", "difficulty": 1},
            {"id": "block-2", "title": f"Core concepts of {topic}", "difficulty": 2},
            {"id": "block-3", "title": f"Deep dive: {topic}", "difficulty": 2},
            {"id": "block-4", "title": f"Practice problems: {topic}", "difficulty": 3},
        ],
        "current_block": "block-1",
    }


def _extract_json(raw: str) -> str:
    """Strip markdown fences if the model ignores instructions."""
    # Remove ```json ... ``` or ``` ... ```
    raw = raw.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", raw)
    if match:
        return match.group(1)
    # Try to find first { ... }
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start != -1 and end > start:
        return raw[start:end]
    return raw


async def generate_lesson_plan(topic: str) -> dict:
    """
    Generate a structured lesson plan for the given topic.

    Returns a dict matching LessonPlan schema.
    Falls back to hardcoded plan on any error.
    """
    if not FEATHERLESS_API_KEY:
        logger.warning("FEATHERLESS_API_KEY not set — using fallback lesson plan")
        return _fallback_plan(topic)

    try:
        client = AsyncOpenAI(
            api_key=FEATHERLESS_API_KEY,
            base_url=FEATHERLESS_BASE_URL,
        )

        response = await client.chat.completions.create(
            model=PLANNER_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": f'Create an adaptive lesson plan for a student who wants to learn: "{topic}"'},
            ],
            temperature=0.2,
            max_tokens=800,
            timeout=20.0,
        )

        raw = response.choices[0].message.content or ""
        plan = json.loads(_extract_json(raw))

        # Validate required keys
        assert "topic" in plan and "blocks" in plan and "current_block" in plan
        assert isinstance(plan["blocks"], list) and len(plan["blocks"]) >= 1

        logger.info("Planner generated %d blocks for topic: %s", len(plan["blocks"]), topic)
        return plan

    except Exception as exc:
        logger.warning("Planner failed (%s) — using fallback plan for topic: %s", exc, topic)
        return _fallback_plan(topic)


# Strategy mapping: cognitive state → (strategy, tone)
_STATE_STRATEGY_MAP = {
    "OVERLOADED": ("step_by_step", "slow"),
    "DISENGAGED": ("re_engage", "encouraging"),
    "FOCUSED":    ("continue", "neutral"),
}


async def update_strategy_for_state(session_id: str, new_state: str) -> None:
    """
    Called when the EEG dwell-time filter confirms a new cognitive state.
    Updates the session's current_strategy (or pending_strategy if speaker is active).

    Uses a heuristic mapping — fast, no API call needed.
    """
    from session.store import session_store, SessionStrategy

    session = session_store.get(session_id)
    if not session:
        return

    strategy_name, tone = _STATE_STRATEGY_MAP.get(new_state, ("continue", "neutral"))
    new_strategy = SessionStrategy(strategy=strategy_name, tone=tone)

    if session.speaker_lock.locked():
        # Speaker is mid-generation — queue the strategy update
        session.pending_strategy = new_strategy
        logger.info(
            "State change %s → strategy '%s' queued (speaker active)",
            new_state, strategy_name,
        )
    else:
        session.current_strategy = new_strategy
        logger.info(
            "State change %s → strategy updated to '%s'",
            new_state, strategy_name,
        )
