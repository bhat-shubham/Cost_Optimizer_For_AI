"""
Pydantic v2 response schemas for AI explanation endpoints.

All fields are strings or string arrays — the LLM produces text,
not numbers. Numerical accuracy comes from the deterministic
context builder, not from LLM output.
"""

from __future__ import annotations

import datetime

from pydantic import BaseModel, Field


class DailyCostExplanation(BaseModel):
    """AI-generated explanation of daily cost behavior."""

    date: datetime.date
    environment: str
    summary: str = Field(
        ...,
        description="Plain-English overview of cost behavior for this day.",
    )
    key_drivers: list[str] = Field(
        default_factory=list,
        description="Bullet-style explanations of main cost contributors.",
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="Optional high-level optimization suggestions.",
    )
