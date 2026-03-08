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
PLANNER_MODEL = os.getenv("PLANNER_MODEL", "meta-llama/Meta-Llama-3.1-70B-Instruct")

_SYSTEM_PROMPT = """You are a curriculum designer. When given a topic, return ONLY valid JSON — no explanation, no markdown fences, no extra text.

The JSON must match this exact schema:
{
  "topic": "<topic string>",
  "blocks": [
    {"id": "block-1", "title": "<specific title>", "difficulty": 1},
    {"id": "block-2", "title": "<specific title>", "difficulty": 2},
    {"id": "block-3", "title": "<specific title>", "difficulty": 2},
    {"id": "block-4", "title": "<specific title>", "difficulty": 3}
  ],
  "current_block": "block-1"
}

Rules:
- 3 to 5 blocks, ascending difficulty (1=introductory, 2=core, 3=advanced/practice)
- Each title must be specific to the topic, not generic
- difficulty must be an integer 1, 2, or 3
- Return ONLY the JSON object, nothing else"""


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
                {"role": "user", "content": f'Generate a lesson plan for: "{topic}"'},
            ],
            temperature=0.3,
            max_tokens=600,
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
