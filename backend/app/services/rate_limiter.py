"""
Postgres-backed rate limiter service.

Enforces per-API-key usage limits using atomic INSERT … ON CONFLICT
counters in the api_key_usage table.

Design decisions:
  • Check BEFORE increment — failed requests (429) don't inflate counters.
  • Atomic upsert — INSERT ON CONFLICT DO UPDATE guarantees no missed
    increments under concurrent requests.
  • Time bucketing — minute = floor to current minute, day = midnight UTC.
  • No Redis — Postgres is sufficient at current scale and keeps the
    architecture simple. Swap in Redis later if needed.

Limits are hard-coded for the free tier. Phase 4 will make them plan-based.
"""

from __future__ import annotations

import datetime
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key_usage import APIKeyUsage

logger = logging.getLogger(__name__)

# ── Free-tier limits (hard-coded for now) ───────────────────
RPM_LIMIT = 60           # requests per minute
RPD_LIMIT = 5_000        # requests per day
AED_LIMIT = 20           # AI explanations per day

# Window type constants
WINDOW_MINUTE = "minute"
WINDOW_DAY = "day"
WINDOW_AI_DAY = "ai_day"


def _minute_bucket(now: datetime.datetime) -> datetime.datetime:
    """Floor a timestamp to the start of the current minute (UTC)."""
    return now.replace(second=0, microsecond=0)


def _day_bucket(now: datetime.datetime) -> datetime.datetime:
    """Floor a timestamp to midnight UTC of the current day."""
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


async def _get_current_count(
    session: AsyncSession,
    api_key_id: uuid.UUID,
    window_type: str,
    window_start: datetime.datetime,
) -> int:
    """Read current request count for a key/window/bucket. Returns 0 if no row."""
    stmt = select(APIKeyUsage.request_count).where(
        APIKeyUsage.api_key_id == api_key_id,
        APIKeyUsage.window_type == window_type,
        APIKeyUsage.window_start == window_start,
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    return row if row is not None else 0


async def _increment(
    session: AsyncSession,
    api_key_id: uuid.UUID,
    window_type: str,
    window_start: datetime.datetime,
) -> None:
    """Atomically increment the counter for a key/window/bucket."""
    stmt = pg_insert(APIKeyUsage).values(
        api_key_id=api_key_id,
        window_type=window_type,
        window_start=window_start,
        request_count=1,
    ).on_conflict_do_update(
        index_elements=["api_key_id", "window_type", "window_start"],
        set_={"request_count": APIKeyUsage.request_count + 1},
    )
    await session.execute(stmt)


class RateLimitExceeded(Exception):
    """Raised when an API key exceeds its rate limit."""


async def check_and_increment_request(
    session: AsyncSession,
    api_key_id: uuid.UUID,
) -> None:
    """
    Check RPM + RPD limits and increment counters if allowed.

    Order: check ALL limits first, then increment ALL.
    This ensures a 429 doesn't partially increment some counters.

    Raises RateLimitExceeded if any limit is breached.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    minute_start = _minute_bucket(now)
    day_start = _day_bucket(now)

    # ── Check limits (read-only) ────────────────────────────
    rpm_count = await _get_current_count(session, api_key_id, WINDOW_MINUTE, minute_start)
    if rpm_count >= RPM_LIMIT:
        raise RateLimitExceeded("RPM limit exceeded")

    rpd_count = await _get_current_count(session, api_key_id, WINDOW_DAY, day_start)
    if rpd_count >= RPD_LIMIT:
        raise RateLimitExceeded("RPD limit exceeded")

    # ── Increment (only after all checks pass) ──────────────
    await _increment(session, api_key_id, WINDOW_MINUTE, minute_start)
    await _increment(session, api_key_id, WINDOW_DAY, day_start)
    await session.commit()  # persist counters — essential for read-only routes


async def check_and_increment_ai_request(
    session: AsyncSession,
    api_key_id: uuid.UUID,
) -> None:
    """
    Check RPM + RPD + AED limits and increment all if allowed.

    AI explanation requests consume from THREE counters:
      - requests/minute
      - requests/day
      - ai_explanations/day

    Raises RateLimitExceeded if any limit is breached.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    minute_start = _minute_bucket(now)
    day_start = _day_bucket(now)

    # ── Check ALL limits first ──────────────────────────────
    rpm_count = await _get_current_count(session, api_key_id, WINDOW_MINUTE, minute_start)
    if rpm_count >= RPM_LIMIT:
        raise RateLimitExceeded("RPM limit exceeded")

    rpd_count = await _get_current_count(session, api_key_id, WINDOW_DAY, day_start)
    if rpd_count >= RPD_LIMIT:
        raise RateLimitExceeded("RPD limit exceeded")

    aed_count = await _get_current_count(session, api_key_id, WINDOW_AI_DAY, day_start)
    if aed_count >= AED_LIMIT:
        raise RateLimitExceeded("AI explanations/day limit exceeded")

    # ── Increment ALL (only after all checks pass) ──────────
    await _increment(session, api_key_id, WINDOW_MINUTE, minute_start)
    await _increment(session, api_key_id, WINDOW_DAY, day_start)
    await _increment(session, api_key_id, WINDOW_AI_DAY, day_start)
    await session.commit()
