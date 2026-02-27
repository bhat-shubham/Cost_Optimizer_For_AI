"""
FastAPI dependency for API key authentication.

Flow:
  1. Extract Bearer token from Authorization header
  2. Hash the token (SHA-256)
  3. Look up api_keys by hash
  4. Verify is_active = true
  5. Load associated Project
  6. Return AuthContext (project + api_key_id)

Security:
  • Generic 401 for ALL failure modes (missing, invalid, inactive)
  • Raw keys are NEVER logged
  • Hash lookup means the DB never sees the raw key

Phase 3.2: Returns AuthContext dataclass instead of bare Project so that
downstream dependencies (rate limiter) can access the api_key_id.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.hashing import hash_api_key
from app.core.database import get_db_session
from app.models.api_key import APIKey
from app.models.project import Project

logger = logging.getLogger(__name__)

# Generic 401 — same message for all auth failures to avoid leaking info
_AUTH_FAILED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or missing API key.",
    headers={"WWW-Authenticate": "Bearer"},
)


@dataclass(frozen=True, slots=True)
class AuthContext:
    """Authenticated request context injected into every protected route.

    Attributes:
        project:    The Project that owns the API key.
        api_key_id: The specific API key UUID used for this request.
                    Used by the rate limiter to track per-key usage.
    """

    project: Project
    api_key_id: uuid.UUID


async def get_current_project(
    authorization: str | None = Header(default=None, alias="Authorization"),
    session: AsyncSession = Depends(get_db_session),
) -> AuthContext:
    """
    FastAPI dependency — resolves Bearer token to an AuthContext.

    Usage in routers:
        Auth = Annotated[AuthContext, Depends(get_current_project)]

    Raises 401 for:
      - Missing Authorization header
      - Non-Bearer scheme
      - Unknown key hash
      - Inactive key
    """

    # ── 1. Extract token ────────────────────────────────────
    if not authorization:
        raise _AUTH_FAILED

    parts = authorization.split(" ", maxsplit=1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise _AUTH_FAILED

    raw_token = parts[1]

    # ── 2. Hash and look up ─────────────────────────────────
    token_hash = hash_api_key(raw_token)

    stmt = (
        select(APIKey)
        .where(APIKey.key_hash == token_hash)
    )
    result = await session.execute(stmt)
    api_key = result.scalar_one_or_none()

    if api_key is None:
        raise _AUTH_FAILED

    # ── 3. Check active ─────────────────────────────────────
    if not api_key.is_active:
        raise _AUTH_FAILED

    # ── 4. Load project ─────────────────────────────────────
    stmt = select(Project).where(Project.id == api_key.project_id)
    result = await session.execute(stmt)
    project = result.scalar_one_or_none()

    if project is None:
        logger.error("API key %s references missing project %s", api_key.id, api_key.project_id)
        raise _AUTH_FAILED

    return AuthContext(project=project, api_key_id=api_key.id)
