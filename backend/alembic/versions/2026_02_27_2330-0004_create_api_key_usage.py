"""create api_key_usage table

Revision ID: 0004
Revises: 0003
Create Date: 2026-02-27

Phase 3.2: Rate limiting usage tracking table.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "api_key_usage",
        sa.Column("api_key_id", sa.UUID(), nullable=False),
        sa.Column("window_type", sa.String(20), nullable=False),
        sa.Column("window_start", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("api_key_id", "window_type", "window_start"),
        sa.ForeignKeyConstraint(["api_key_id"], ["api_keys.id"], ondelete="CASCADE"),
    )
    # Composite index for fast lookups during rate limit checks
    op.create_index(
        "ix_api_key_usage_lookup",
        "api_key_usage",
        ["api_key_id", "window_type", "window_start"],
    )


def downgrade() -> None:
    op.drop_index("ix_api_key_usage_lookup", table_name="api_key_usage")
    op.drop_table("api_key_usage")
