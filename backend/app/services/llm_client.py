"""
Groq LLM client for generating cost explanations.

Uses Groq's OpenAI-compatible /chat/completions API via httpx.
The LLM ONLY narrates pre-computed facts — it never calculates.

Configuration:
  GROQ_API_KEY — server-side only (never exposed to clients)
  LLM_MODEL    — defaults to llama-3.1-8b-instant (fast, cheap)

Safety:
  • Low temperature (0.2) for consistent output
  • Bounded max_tokens (512)
  • System prompt explicitly forbids hallucination
  • Structured JSON output requested
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# ── System prompt ───────────────────────────────────────────
SYSTEM_PROMPT = """\
You are explaining AI infrastructure cost to an engineer.
Be precise, factual, and conservative. Use ONLY the data provided.

RULES:
1. NEVER invent, estimate, or round numbers.
2. Model and endpoint describe the SAME cost from different angles.
   They are NOT independent contributors. NEVER say "both contributed"
   or "each accounted for". Instead say "attributable to [model] via [endpoint]".
3. key_drivers must add NEW info not already in the summary. Do NOT repeat
   total cost, tokens, or request count if the summary already states them.
4. If usage is low (≤5 requests or cost <$1), do NOT suggest optimization.
   Say "No immediate optimization needed" or "Continue monitoring".

EXAMPLE — single model, single endpoint, 1 request:
{
  "summary": "Today's AI cost is $0.024, with 650 tokens used across 1 request in dev.",
  "key_drivers": [
    "All cost is attributable to gpt-4 via the /chat/summarize endpoint."
  ],
  "recommendations": [
    "No immediate optimization is required at this volume; continue monitoring as usage grows."
  ]
}

BAD key_drivers (NEVER do this):
  ❌ "The top model and endpoint both had a cost of $0.024"
  ❌ "The request count is 1, indicating low activity"
  ❌ "gpt-4 contributed $0.024 and /chat/summarize contributed $0.024"

GOOD key_drivers:
  ✅ "All cost is attributable to gpt-4 via the /chat/summarize endpoint."
  ✅ "gpt-4 accounted for 100% of spend, handling 650 tokens in a single call."

If there is no previous day, call it a baseline day.
If cost is zero, say so clearly.
Respond with valid JSON only — no markdown fences, no extra text.\
"""


async def generate_explanation(
    context: dict[str, Any],
) -> dict[str, Any]:
    """
    Call Groq's LLM to narrate the pre-computed cost context.

    Args:
        context: Structured facts dict from build_daily_cost_context().

    Returns:
        Dict with keys: summary, key_drivers, recommendations.

    Raises:
        RuntimeError: If the LLM call fails or returns unparseable output.
    """
    if not settings.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not configured")

    user_message = (
        "Here is today's AI cost data. Explain it using ONLY these facts:\n\n"
        + json.dumps(context, indent=2)
    )

    payload = {
        "model": settings.LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.2,
        "max_tokens": 512,
    }

    headers = {
        "Authorization": f"Bearer {settings.GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{_GROQ_BASE_URL}/chat/completions",
            json=payload,
            headers=headers,
        )

    if response.status_code != 200:
        logger.error(
            "Groq API error: status=%d body=%s",
            response.status_code,
            response.text[:500],
        )
        raise RuntimeError("LLM service returned an error")

    # ── Parse the LLM's JSON response ───────────────────────
    try:
        data = response.json()
        content = data["choices"][0]["message"]["content"]

        # Strip markdown fences if the model wraps output
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]  # drop first line
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

        parsed = json.loads(content)
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        logger.error("Failed to parse LLM response: %s", exc)
        raise RuntimeError("Could not parse LLM explanation") from exc

    # ── Validate structure ──────────────────────────────────
    return {
        "summary": parsed.get("summary", "No summary available."),
        "key_drivers": parsed.get("key_drivers", []),
        "recommendations": parsed.get("recommendations", []),
    }
