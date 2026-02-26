"""
Ingestion router — the single entry point for AI usage telemetry.

POST /ingest/usage
  1. Validates the payload (Pydantic).
  2. Computes total_tokens and cost_usd server-side.
  3. Persists the event via async SQLAlchemy.
  4. Returns the stored record with 201 Created.

No auth, no rate limiting, no batching — those come in later phases.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.models.usage import UsageEvent
from app.schemas.usage import UsageEventCreate, UsageEventResponse
from app.services.cost_calculator import calculate_cost

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Ingestion"])

# Type alias for cleaner signatures
DbSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.post(
    "/usage",
    response_model=UsageEventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a single AI usage event",
    description=(
        "Accepts a usage payload, calculates cost server-side, "
        "and persists the event as a financial-grade record."
    ),
)
async def ingest_usage_event(
    payload: UsageEventCreate,
    session: DbSession,
) -> UsageEvent:
    """
    Core ingestion endpoint.

    The client NEVER supplies cost or total_tokens — those are
    derived here to prevent manipulation.
    """

    # ── 1. Calculate cost (service layer) ───────────────────
    try:
        cost_usd = calculate_cost(
            model_name=payload.model_name,
            input_tokens=payload.input_tokens,
            output_tokens=payload.output_tokens,
        )
    except ValueError as exc:
        # Unknown model → 422 (client can fix the request)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    # ── 2. Derive total tokens ──────────────────────────────
    total_tokens = payload.input_tokens + payload.output_tokens

    # ── 3. Build the ORM record ─────────────────────────────
    event = UsageEvent(
        provider=payload.provider,
        model_name=payload.model_name,
        input_tokens=payload.input_tokens,
        output_tokens=payload.output_tokens,
        total_tokens=total_tokens,
        cost_usd=cost_usd,
        latency_ms=payload.latency_ms,
        endpoint=payload.endpoint,
        environment=payload.environment,
        user_id=payload.user_id,
        metadata_=payload.metadata,
    )

    # ── 4. Persist ──────────────────────────────────────────
    try:
        session.add(event)
        await session.commit()
        await session.refresh(event)
    except Exception:
        await session.rollback()
        # Log the real error internally; return a generic message
        logger.exception("Failed to persist usage event")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store the usage event. Please try again.",
        )

    return event
