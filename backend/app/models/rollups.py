"""
SQLAlchemy models for rollup (pre-aggregated) tables.

These are derived from usage_events and exist solely for fast analytics reads.
usage_events remains the source of truth — rollups are reproducible.

Design notes:
  • Composite primary keys encode the GROUP BY dimensions, making
    INSERT … ON CONFLICT idempotent by construction.
  • NUMERIC(12,8) for cost — same precision as usage_events.
  • BIGINT for total_tokens — rollups sum across many events.
  • updated_at tracks when the rollup was last refreshed.
"""

import datetime

from sqlalchemy import BigInteger, Date, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DailyCostRollup(Base):
    """
    Pre-aggregated daily cost, grouped by (date, environment).

    PK: (date, environment)
    """

    __tablename__ = "daily_cost_rollups"

    date: Mapped[datetime.date] = mapped_column(
        Date, primary_key=True,
    )
    environment: Mapped[str] = mapped_column(
        String(10), primary_key=True,
    )
    total_cost_usd: Mapped[float] = mapped_column(
        Numeric(12, 8), nullable=False,
    )
    total_tokens: Mapped[int] = mapped_column(
        BigInteger, nullable=False,
    )
    request_count: Mapped[int] = mapped_column(
        Integer, nullable=False,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ModelCostRollup(Base):
    """
    Pre-aggregated cost by model, grouped by (date, model_name, environment).

    PK: (date, model_name, environment)
    """

    __tablename__ = "model_cost_rollups"

    date: Mapped[datetime.date] = mapped_column(
        Date, primary_key=True,
    )
    model_name: Mapped[str] = mapped_column(
        String(100), primary_key=True,
    )
    environment: Mapped[str] = mapped_column(
        String(10), primary_key=True,
    )
    total_cost_usd: Mapped[float] = mapped_column(
        Numeric(12, 8), nullable=False,
    )
    total_tokens: Mapped[int] = mapped_column(
        BigInteger, nullable=False,
    )
    request_count: Mapped[int] = mapped_column(
        Integer, nullable=False,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class EndpointCostRollup(Base):
    """
    Pre-aggregated cost by endpoint, grouped by (date, endpoint, environment).

    PK: (date, endpoint, environment)
    """

    __tablename__ = "endpoint_cost_rollups"

    date: Mapped[datetime.date] = mapped_column(
        Date, primary_key=True,
    )
    endpoint: Mapped[str] = mapped_column(
        String(255), primary_key=True,
    )
    environment: Mapped[str] = mapped_column(
        String(10), primary_key=True,
    )
    total_cost_usd: Mapped[float] = mapped_column(
        Numeric(12, 8), nullable=False,
    )
    request_count: Mapped[int] = mapped_column(
        Integer, nullable=False,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
