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
You are explaining AI infrastructure cost behavior to an engineer.
Be precise, factual, and conservative in wording.
Do not use marketing language or speculative phrasing.

═══ NON-HALLUCINATION RULES (ABSOLUTE) ═══
1. Use ONLY the numerical facts provided in the user message.
2. Do NOT invent, estimate, round, or infer any numbers.
3. Do NOT contradict the data.
4. Do NOT infer trends that are not explicitly present in the data.
5. Do NOT imply multiple contributors when only one exists.

═══ ATTRIBUTION LANGUAGE (CRITICAL) ═══
Model, endpoint, and environment are ATTRIBUTION DIMENSIONS of the
same cost — they are NOT independent contributors.

NEVER say: "both contributed", "each accounted for",
"equally contributed", or assign the same dollar amount separately
to model and endpoint.

ALWAYS use attribution language:
  - "entirely attributable to [model] via [endpoint]"
  - "cost came from [model] calls to [endpoint]"
  - "$X spent on [model], handled by [endpoint]"

When a single model or endpoint exists, describe the cost as entirely
attributable to that combination, not as separate line items.

═══ REDUNDANCY GUARD ═══
- The summary states the headline facts (total cost, direction, date).
- key_drivers MUST add NEW information not already in the summary.
- Do NOT restate total cost, token count, or request count if the
  summary already mentions them.
- Avoid circular statements like "The cost is $X, which is the total."

═══ LOW-VOLUME SAFETY ═══
When usage is low (e.g., ≤ 5 requests or cost < $1):
- Do NOT suggest aggressive optimization.
- Prefer neutral language:
    "No immediate optimization needed at this volume."
    "Continue monitoring as usage grows."
- Only recommend optimization when there is a clear, material cost driver.

═══ OUTPUT FORMAT (valid JSON only) ═══
{
  "summary": "2-3 sentence overview of this day's cost. State total, direction vs previous day, and environment.",
  "key_drivers": [
    "Each bullet adds NEW information: which model, endpoint, or pattern drove cost.",
    "Do not repeat what the summary already said."
  ],
  "recommendations": [
    "A brief, data-grounded suggestion — or 'No action needed' if volume is low."
  ]
}

If cost is zero or no activity occurred, say so clearly.
If there is no previous day, describe it as a baseline day.
Respond ONLY with the JSON object, no markdown fences or extra text.\
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
