"""
Pydantic v2 response schemas for analytics endpoints.

All monetary fields use Decimal — no floats anywhere.
All schemas use from_attributes=True so SQLAlchemy Row objects
returned by Core select() map directly without manual conversion.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class DailyCostOut(BaseModel):
    """One row of the daily cost aggregation."""

    model_config = ConfigDict(from_attributes=True)

    date: datetime.date
    total_cost_usd: Decimal


class CostByModelOut(BaseModel):
    """Cost breakdown for a single model."""

    model_config = ConfigDict(from_attributes=True)

    model_name: str
    total_cost_usd: Decimal
    total_tokens: int
    request_count: int


class CostByEndpointOut(BaseModel):
    """Cost breakdown for a single application endpoint."""

    model_config = ConfigDict(from_attributes=True)

    endpoint: str
    total_cost_usd: Decimal
    request_count: int
