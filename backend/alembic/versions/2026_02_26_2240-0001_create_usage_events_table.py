"""create usage_events table

Revision ID: 0001
Revises: 
Create Date: 2026-02-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "usage_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "timestamp",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Numeric(12, 8), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("endpoint", sa.String(255), nullable=False),
        sa.Column("environment", sa.String(10), nullable=False),
        sa.Column("user_id", sa.String(255), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("input_tokens >= 0", name="ck_input_tokens_non_neg"),
        sa.CheckConstraint("output_tokens >= 0", name="ck_output_tokens_non_neg"),
        sa.CheckConstraint("total_tokens >= 0", name="ck_total_tokens_non_neg"),
        sa.CheckConstraint("latency_ms >= 0", name="ck_latency_ms_non_neg"),
        sa.CheckConstraint(
            "environment IN ('dev', 'prod')", name="ck_environment_valid"
        ),
    )

    # Indexes for analytics queries
    op.create_index("ix_usage_events_timestamp", "usage_events", ["timestamp"])
    op.create_index("ix_usage_events_provider", "usage_events", ["provider"])
    op.create_index("ix_usage_events_model_name", "usage_events", ["model_name"])
    op.create_index("ix_usage_events_environment", "usage_events", ["environment"])


def downgrade() -> None:
    op.drop_index("ix_usage_events_environment", table_name="usage_events")
    op.drop_index("ix_usage_events_model_name", table_name="usage_events")
    op.drop_index("ix_usage_events_provider", table_name="usage_events")
    op.drop_index("ix_usage_events_timestamp", table_name="usage_events")
    op.drop_table("usage_events")
