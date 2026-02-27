"""
FastAPI dependencies for rate limit enforcement.

Two dependencies:
  • enforce_rate_limit     — for ingest + analytics (RPM + RPD)
  • enforce_ai_rate_limit  — for AI explain (RPM + RPD + AED)

Both depend on get_current_project (auth runs first), then check limits.
Order in request pipeline: AUTH → RATE LIMIT → ROUTER LOGIC.

On limit exceeded, returns 429 with a generic message.
We intentionally do NOT expose remaining quota or retry-after headers
to avoid giving abuse scripts precise timing information.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import AuthContext, get_current_project
from app.core.database import get_db_session
from app.services.rate_limiter import (
    RateLimitExceeded,
    check_and_increment_ai_request,
    check_and_increment_request,
)

_RATE_LIMITED = HTTPException(
    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
    detail="Rate limit exceeded. Please try again later.",
)


async def enforce_rate_limit(
    auth: AuthContext = Depends(get_current_project),
    session: AsyncSession = Depends(get_db_session),
) -> AuthContext:
    """
    Enforce RPM + RPD limits for standard endpoints.

    Returns the AuthContext so routers can access project/api_key_id.
    """
    try:
        await check_and_increment_request(session, auth.api_key_id)
    except RateLimitExceeded:
        raise _RATE_LIMITED

    return auth


async def enforce_ai_rate_limit(
    auth: AuthContext = Depends(get_current_project),
    session: AsyncSession = Depends(get_db_session),
) -> AuthContext:
    """
    Enforce RPM + RPD + AED limits for AI explanation endpoints.

    AI endpoints consume from both the general request pool AND
    the AI-specific daily cap.
    """
    try:
        await check_and_increment_ai_request(session, auth.api_key_id)
    except RateLimitExceeded:
        raise _RATE_LIMITED

    return auth
