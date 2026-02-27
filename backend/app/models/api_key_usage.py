"""
API key usage tracking model for rate limiting.

Each row represents the request count for one API key in one time window.
Composite PK: (api_key_id, window_type, window_start) — one row per bucket.

Time buckets:
  • 'minute' — floor to current minute (RPM tracking)
  • 'day'    — floor to midnight UTC (RPD + AED tracking)

Atomic increments via INSERT … ON CONFLICT DO UPDATE ensure correctness
under concurrent requests without external locks.
"""

import uuid
import datetime

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class APIKeyUsage(Base):
    """Per-key, per-window request counter for rate limiting."""

    __tablename__ = "api_key_usage"

    api_key_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("api_keys.id", ondelete="CASCADE"),
        primary_key=True,
    )
    window_type: Mapped[str] = mapped_column(
        String(20),
        primary_key=True,
    )
    window_start: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        primary_key=True,
    )
    request_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    def __repr__(self) -> str:
        return (
            f"<APIKeyUsage key={self.api_key_id!s:.8} "
            f"type={self.window_type} count={self.request_count}>"
        )
