"""
Pydantic v2 schemas for usage-event ingestion.

Separation:
  • UsageEventCreate  — what the CLIENT sends (no cost, no total_tokens).
  • UsageEventResponse — what the SERVER returns after persistence.

This enforces the rule: the frontend can REQUEST, the backend DECIDES.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# ── Request schema ──────────────────────────────────────────
class UsageEventCreate(BaseModel):
    """
    Payload accepted by POST /ingest/usage.

    cost_usd and total_tokens are intentionally absent —
    they are computed server-side and must never be trusted
    from the client.

    extra="forbid" ensures unknown fields (e.g. a fake cost_usd)
    are rejected with 422, not silently ignored.
    """

    model_config = ConfigDict(extra="forbid")

    provider: str = Field(
        ...,
        min_length=1,
        max_length=50,
        examples=["openai", "anthropic", "groq"],
        description="AI provider identifier.",
    )
    model_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        examples=["gpt-4", "gpt-3.5-turbo", "llama-3-70b"],
        description="Model used for this call.",
    )
    input_tokens: int = Field(
        ...,
        ge=0,
        examples=[500],
        description="Number of prompt/input tokens.",
    )
    output_tokens: int = Field(
        ...,
        ge=0,
        examples=[150],
        description="Number of completion/output tokens.",
    )
    latency_ms: int = Field(
        ...,
        ge=0,
        examples=[1200],
        description="End-to-end latency of the AI call in milliseconds.",
    )
    endpoint: str = Field(
        ...,
        min_length=1,
        max_length=255,
        examples=["/chat/summarize"],
        description="Application endpoint that triggered this call.",
    )
    environment: Literal["dev", "prod"] = Field(
        ...,
        examples=["dev"],
        description="Deployment environment.",
    )
    user_id: str | None = Field(
        default=None,
        max_length=255,
        examples=["user-123"],
        description="User who initiated the call (nullable for now).",
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        examples=[{"temperature": 0.7, "max_tokens": 256}],
        description="Arbitrary prompt-level parameters (JSONB).",
    )


# ── Response schema ─────────────────────────────────────────
class UsageEventResponse(BaseModel):
    """
    Full record returned after a usage event is persisted.

    Includes server-generated fields: id, timestamp, total_tokens, cost_usd.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    timestamp: datetime
    provider: str
    model_name: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: Decimal
    latency_ms: int
    endpoint: str
    environment: str
    user_id: str | None
    metadata: dict[str, Any] | None = Field(
        default=None,
        # Maps to the ORM attribute `metadata_` (column name is `metadata`)
        validation_alias="metadata_",
    )
