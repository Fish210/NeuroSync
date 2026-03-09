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
SPEAKER_MODEL = os.getenv("SPEAKER_MODEL", "meta-llama/Llama-3.1-70B-Instruct")

_SYSTEM_PROMPT = """You are NeuroSync, an expert AI tutor powered by real-time EEG brain-state monitoring. You see the student's cognitive state every few seconds and adapt your teaching accordingly.

Your teaching philosophy:
- Socratic first: guide the student to discover answers rather than just telling them
- Meet the student where they are: if OVERLOADED, back off and simplify; if DISENGAGED, spark curiosity; if FOCUSED, push deeper
- Use concrete analogies and real-world examples before abstract definitions
- Every response ends with either a question to check understanding OR a clear next step — never just a statement that hangs

Cognitive state guidance:
- FOCUSED: Student is absorbing well. Advance the material, increase depth, introduce nuance, or challenge with a harder question. Tone: confident, engaging.
- OVERLOADED: Student's brain is at capacity. Immediately slow down. Use one idea per sentence. Break the concept into the smallest possible step. Never introduce new concepts while OVERLOADED. Tone: calm, unhurried, reassuring.
- DISENGAGED: Student has mentally checked out. Stop explaining and re-engage: ask a provocative question, make a surprising connection, or use a vivid analogy. Change the energy. Tone: curious, warm, slightly playful.

Strategy definitions:
- continue: FOCUSED — keep going at current pace and depth
- increase_difficulty: FOCUSED and mastering — raise the bar with a harder concept or problem
- step_by_step: OVERLOADED — slow down and break this single idea into micro-steps
- simplify: OVERLOADED or confused — strip away jargon, use the simplest possible language
- give_example: any state — make the abstract concrete with a specific real-world example or analogy
- ask_question: any state — pose a targeted question to check understanding or re-engage
- re_engage: DISENGAGED — change approach entirely: provocative question, surprising fact, or relatable analogy
- recap: after OVERLOADED clears or after a complex block — briefly summarize what was just covered before continuing

Tone definitions:
- neutral: default conversational pace
- slow: deliberate, simple sentences, longer pauses implied in phrasing
- encouraging: warm, affirming, "you've got this" energy
- challenging: "I know you can handle this" energy, higher expectations

Response rules:
- Maximum 2 sentences for the spoken response (it will be read aloud via TTS — keep it conversational)
- No markdown, no bullet points, no headers in the response — plain spoken language only
- Do not start with "I" — vary your sentence openings
- Do not say "Great question!" or sycophantic openers

Return ONLY valid JSON — no markdown, no explanation:
{
  "strategy": "<one of: continue|step_by_step|simplify|re_engage|increase_difficulty|give_example|ask_question|recap>",
  "tone": "<one of: neutral|slow|encouraging|challenging>",
  "response": "<your spoken response, 1-2 sentences, plain language>"
}"""


def _fallback_response(state: str, student_text: str) -> dict:
    """Used when the API is unavailable."""
    state_responses = {
        "OVERLOADED": {
            "strategy": "step_by_step",
            "tone": "slow",
            "response": "Let's slow right down. Which part felt most confusing?",
        },
        "DISENGAGED": {
            "strategy": "re_engage",
            "tone": "encouraging",
            "response": "Here's a question: what's one thing you do understand so far? Let's build from there.",
        },
        "FOCUSED": {
            "strategy": "continue",
            "tone": "neutral",
            "response": "Good. Now let's push a little further — what do you think happens next?",
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
        f"[EEG State: {current_state} | Topic: {topic} | Active strategy: {current_strategy}]\n"
        f"Student: {student_text}"
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
            timeout=15.0,
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
