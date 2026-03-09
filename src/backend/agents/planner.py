"""
Lesson plan generator.

Calls the configured planner model to produce a structured lesson plan.
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
PLANNER_API_KEY = os.getenv("PLANNER_API_KEY", FEATHERLESS_API_KEY)
PLANNER_BASE_URL = os.getenv("PLANNER_BASE_URL", FEATHERLESS_BASE_URL)
PLANNER_MODEL = os.getenv("PLANNER_MODEL", "models/gemini-3.1-pro-preview")

_SYSTEM_PROMPT = """You are NeuroSync's lead curriculum architect. Design a lesson plan for one live tutoring session where the tutor adapts every few seconds to EEG state changes: FOCUSED, OVERLOADED, and DISENGAGED.

Your plan must feel like a strong human tutor prepared it in advance, not like a generic outline.

Design principles:
- Start concrete, then become more abstract only after the foundation is in place.
- Apply Bloom's Taxonomy: begin with recall/comprehension (difficulty 1), move to application/analysis (difficulty 2), and finish with synthesis/evaluation or practice (difficulty 3).
- Every block should correspond to a teachable 5–10 minute segment with a clear stopping point.
- Build incrementally: each block should rely on the previous block.
- Favor tangible mental models, worked examples, and misconception-resistant ordering.
- The last block must always be practice, retrieval, or a direct check for understanding.
- Titles must be precise and vivid. Avoid generic titles like "Introduction to X" or "Advanced Concepts".

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
- Every title must be specific enough that a tutor immediately knows what to teach in that block
- Avoid duplicate or overlapping blocks
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


def _normalize_plan(topic: str, plan: dict) -> dict:
    """Coerce provider output into the app's strict LessonPlan shape."""
    raw_blocks = plan.get("blocks")
    if not isinstance(raw_blocks, list) or not raw_blocks:
        raise ValueError("Planner returned no blocks")

    normalized_blocks = []
    for idx, block in enumerate(raw_blocks[:6], start=1):
        title = ""
        if isinstance(block, dict):
            title = str(block.get("title", "")).strip()
        if not title:
            title = f"{topic}: block {idx}"

        if idx == 1:
            difficulty = 1
        elif idx == len(raw_blocks[:6]):
            difficulty = 3
        else:
            difficulty = 2

        normalized_blocks.append(
            {
                "id": f"block-{idx}",
                "title": title,
                "difficulty": difficulty,
            }
        )

    while len(normalized_blocks) < 4:
        idx = len(normalized_blocks) + 1
        normalized_blocks.append(
            {
                "id": f"block-{idx}",
                "title": f"{topic}: block {idx}",
                "difficulty": 3 if idx == 4 else 2,
            }
        )

    normalized_blocks[0]["difficulty"] = 1
    normalized_blocks[-1]["difficulty"] = 3

    return {
        "topic": topic,
        "blocks": normalized_blocks,
        "current_block": "block-1",
    }


async def generate_lesson_plan(topic: str) -> dict:
    """
    Generate a structured lesson plan for the given topic.

    Returns a dict matching LessonPlan schema.
    Falls back to hardcoded plan on any error.
    """
    if not PLANNER_API_KEY:
        logger.warning("PLANNER_API_KEY not set — using fallback lesson plan")
        return _fallback_plan(topic)

    try:
        client = AsyncOpenAI(
            api_key=PLANNER_API_KEY,
            base_url=PLANNER_BASE_URL,
            max_retries=0,
        )

        request_kwargs = {
            "model": PLANNER_MODEL,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f'Create an adaptive lesson plan for a student who wants to learn "{topic}". '
                        "Make the progression concrete, cumulative, and immediately teachable."
                    ),
                },
            ],
            "temperature": 0.2,
            "timeout": 20.0,
        }
        if "generativelanguage.googleapis.com" in PLANNER_BASE_URL:
            request_kwargs["max_completion_tokens"] = 1500
            request_kwargs["response_format"] = {"type": "json_object"}
        else:
            request_kwargs["max_tokens"] = 800

        response = await client.chat.completions.create(
            **request_kwargs,
        )

        raw = response.choices[0].message.content or ""
        plan = _normalize_plan(topic, json.loads(_extract_json(raw)))

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
