"""
API key model — authentication credential for a project.

Security notes:
  • Raw API keys are NEVER stored. Only a SHA-256 hash is persisted.
  • The `prefix` column stores the first 8 characters (e.g., "sk_live_")
    for identification in logs/UI without exposing the full key.
  • `is_active` allows key revocation without deletion (audit trail).
"""

import uuid
import datetime

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class APIKey(Base):
    """Hashed API key belonging to a project."""

    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key_hash: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        unique=True,
    )
    prefix: Mapped[str] = mapped_column(
        String(12),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"<APIKey id={self.id!s:.8} prefix={self.prefix!r} "
            f"active={self.is_active}>"
        )
