"""
Speaker agent.

Calls Featherless 7-8B model to generate the tutor's next response.
Receives student speech + current cognitive state + conversation history.
Returns: { strategy, tone, response }

Target latency: <1.5s
Called from: api/websocket.py on STUDENT_SPEECH events
"""
from __future__ import annotations

import json
import logging
import os
import re
import time

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

FEATHERLESS_API_KEY = os.getenv("FEATHERLESS_API_KEY", "")
FEATHERLESS_BASE_URL = os.getenv("FEATHERLESS_BASE_URL", "https://api.featherless.ai/v1")
SPEAKER_MODEL = os.getenv("SPEAKER_MODEL", "Qwen/Qwen2.5-7B-Instruct")

_SYSTEM_PROMPT = """You are an adaptive AI tutor. Based on the student's message and their current cognitive state, generate a tutoring response.

Return ONLY valid JSON:
{
  "strategy": "<one of: continue|step_by_step|simplify|re_engage|increase_difficulty>",
  "tone": "<one of: neutral|slow|encouraging|challenging>",
  "response": "<your spoken response to the student, 1-3 sentences>"
}

Strategy guide:
- continue: student is FOCUSED and progressing well
- step_by_step: student is OVERLOADED — break it down
- simplify: student is confused — use simpler language
- re_engage: student is DISENGAGED — ask a question, change approach
- increase_difficulty: student mastered the concept — raise the bar

Tone guide:
- neutral: default
- slow: for OVERLOADED students
- encouraging: for DISENGAGED students
- challenging: for students ready for more

Keep responses concise and conversational. Return ONLY the JSON object."""


def _fallback_response(state: str, student_text: str) -> dict:
    """Used when the API is unavailable."""
    state_responses = {
        "OVERLOADED": {
            "strategy": "step_by_step",
            "tone": "slow",
            "response": "Let's slow down. Can you tell me which part is unclear?",
        },
        "DISENGAGED": {
            "strategy": "re_engage",
            "tone": "encouraging",
            "response": "Let's try a different angle. What do you already know about this?",
        },
        "FOCUSED": {
            "strategy": "continue",
            "tone": "neutral",
            "response": "Good thinking. Let's keep going — what happens next?",
        },
    }
    return state_responses.get(state, state_responses["FOCUSED"])


def _extract_json(raw: str) -> str:
    raw = raw.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", raw)
    if match:
        return match.group(1)
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start != -1 and end > start:
        return raw[start:end]
    return raw


def _build_messages(
    student_text: str,
    current_state: str,
    current_strategy: str,
    topic: str,
    conversation: list[dict],
) -> list[dict]:
    """Build the messages list for the API call."""
    messages = [{"role": "system", "content": _SYSTEM_PROMPT}]

    # Add recent conversation history (last 6 turns)
    for turn in conversation[-6:]:
        role = "assistant" if turn["speaker"] == "tutor" else "user"
        messages.append({"role": role, "content": turn["text"]})

    # Current student message with context
    context = (
        f"[Topic: {topic} | Student cognitive state: {current_state} | "
        f"Current strategy: {current_strategy}]\n\n"
        f"Student says: {student_text}"
    )
    messages.append({"role": "user", "content": context})
    return messages


async def generate_response(
    student_text: str,
    current_state: str,
    current_strategy: str,
    topic: str,
    conversation: list[dict],
) -> dict:
    """
    Generate tutor response to student speech.

    Returns dict with keys: strategy, tone, response
    Falls back to hardcoded response on any error.
    """
    if not FEATHERLESS_API_KEY:
        logger.warning("FEATHERLESS_API_KEY not set — using fallback speaker response")
        return _fallback_response(current_state, student_text)

    start_time = time.monotonic()

    try:
        client = AsyncOpenAI(
            api_key=FEATHERLESS_API_KEY,
            base_url=FEATHERLESS_BASE_URL,
        )

        messages = _build_messages(
            student_text, current_state, current_strategy, topic, conversation
        )

        response = await client.chat.completions.create(
            model=SPEAKER_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=200,
            timeout=8.0,
        )

        raw = response.choices[0].message.content or ""
        result = json.loads(_extract_json(raw))

        # Validate required keys
        assert "strategy" in result and "tone" in result and "response" in result

        elapsed = time.monotonic() - start_time
        logger.info(
            "Speaker response in %.2fs: strategy=%s tone=%s",
            elapsed, result["strategy"], result["tone"],
        )
        return result

    except Exception as exc:
        elapsed = time.monotonic() - start_time
        logger.warning("Speaker failed after %.2fs (%s) — using fallback", elapsed, exc)
        return _fallback_response(current_state, student_text)
