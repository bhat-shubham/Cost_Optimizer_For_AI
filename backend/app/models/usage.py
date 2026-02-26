"""
SQLAlchemy model for the `usage_events` table.

Each row represents a single AI/LLM API call — treated as a financial
transaction, not a throwaway log entry.

Design notes:
  • cost_usd uses NUMERIC(12,8) — exact decimal arithmetic, no float rounding.
  • metadata_ is JSONB for flexible prompt-level params (temperature, max_tokens, …).
  • Indexes on timestamp, provider, model_name, environment support the
    analytics queries coming in later phases.
"""

import uuid

from sqlalchemy import (
    CheckConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID, TIMESTAMP
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UsageEvent(Base):
    """One AI API call with server-calculated cost."""

    __tablename__ = "usage_events"

    # ── Primary key ─────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )

    # ── Timestamp ───────────────────────────────────────────
    timestamp: Mapped[uuid.UUID] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # ── Provider / model ────────────────────────────────────
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)

    # ── Token counts ────────────────────────────────────────
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False)

    # ── Cost (exact decimal — financial data) ───────────────
    cost_usd: Mapped[float] = mapped_column(
        Numeric(12, 8),
        nullable=False,
    )

    # ── Call metadata ───────────────────────────────────────
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    environment: Mapped[str] = mapped_column(String(10), nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Column named `metadata_` to avoid shadowing Python's built-in;
    # maps to DB column `metadata`.
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
    )

    # ── Table-level constraints ─────────────────────────────
    __table_args__ = (
        CheckConstraint("input_tokens >= 0", name="ck_input_tokens_non_neg"),
        CheckConstraint("output_tokens >= 0", name="ck_output_tokens_non_neg"),
        CheckConstraint("total_tokens >= 0", name="ck_total_tokens_non_neg"),
        CheckConstraint("latency_ms >= 0", name="ck_latency_ms_non_neg"),
        CheckConstraint(
            "environment IN ('dev', 'prod')",
            name="ck_environment_valid",
        ),
        Index("ix_usage_events_timestamp", "timestamp"),
        Index("ix_usage_events_provider", "provider"),
        Index("ix_usage_events_model_name", "model_name"),
        Index("ix_usage_events_environment", "environment"),
    )

    def __repr__(self) -> str:
        return (
            f"<UsageEvent id={self.id!s:.8} model={self.model_name} "
            f"cost=${self.cost_usd}>"
        )
