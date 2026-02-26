"""
Server-side cost calculation for AI model usage.

WHY THIS IS A SERVICE AND NOT INLINE:
  • Cost is financial data — it deserves its own testable, auditable module.
  • Pricing changes (or fetching from a DB/API later) won't touch the router.
  • Using Decimal everywhere avoids floating-point rounding on money.

PHASE 1: Prices are hardcoded. Clearly documented so they can be replaced
with a database lookup or provider API in later phases.
"""

from decimal import Decimal

# ── Pricing table ───────────────────────────────────────────
# Per-1K-token prices in USD.
# Source: https://openai.com/pricing (snapshot — will be replaced by
# a dynamic lookup in Phase 2).
#
# Format: model_name -> { "input": Decimal, "output": Decimal }

MODEL_PRICING: dict[str, dict[str, Decimal]] = {
    # OpenAI
    "gpt-4": {
        "input": Decimal("0.03"),
        "output": Decimal("0.06"),
    },
    "gpt-4-turbo": {
        "input": Decimal("0.01"),
        "output": Decimal("0.03"),
    },
    "gpt-3.5-turbo": {
        "input": Decimal("0.0005"),
        "output": Decimal("0.0015"),
    },
    # Anthropic
    "claude-3-opus": {
        "input": Decimal("0.015"),
        "output": Decimal("0.075"),
    },
    "claude-3-sonnet": {
        "input": Decimal("0.003"),
        "output": Decimal("0.015"),
    },
    "claude-3-haiku": {
        "input": Decimal("0.00025"),
        "output": Decimal("0.00125"),
    },
    # Groq (Llama-hosted)
    "llama-3-70b": {
        "input": Decimal("0.00059"),
        "output": Decimal("0.00079"),
    },
    "llama-3-8b": {
        "input": Decimal("0.00005"),
        "output": Decimal("0.00008"),
    },
    # Google
    "gemini-1.5-pro": {
        "input": Decimal("0.00125"),
        "output": Decimal("0.005"),
    },
    "gemini-1.5-flash": {
        "input": Decimal("0.000075"),
        "output": Decimal("0.0003"),
    },
}

# Pre-computed divisor — avoids repeated Decimal construction.
_ONE_THOUSAND = Decimal("1000")


def get_supported_models() -> list[str]:
    """Return a sorted list of model names with known pricing."""
    return sorted(MODEL_PRICING.keys())


def calculate_cost(
    model_name: str,
    input_tokens: int,
    output_tokens: int,
) -> Decimal:
    """
    Calculate the USD cost of an AI call.

    Args:
        model_name:    Identifier matching a key in MODEL_PRICING.
        input_tokens:  Number of prompt tokens (>= 0).
        output_tokens: Number of completion tokens (>= 0).

    Returns:
        Exact Decimal cost in USD.

    Raises:
        ValueError: If model_name is not in the pricing table.
    """
    pricing = MODEL_PRICING.get(model_name)
    if pricing is None:
        supported = ", ".join(get_supported_models())
        raise ValueError(
            f"Unknown model '{model_name}'. "
            f"Supported models: {supported}"
        )

    input_cost = (Decimal(input_tokens) / _ONE_THOUSAND) * pricing["input"]
    output_cost = (Decimal(output_tokens) / _ONE_THOUSAND) * pricing["output"]

    return input_cost + output_cost
