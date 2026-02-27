"""create rollup tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── daily_cost_rollups ──────────────────────────────────
    op.create_table(
        "daily_cost_rollups",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("environment", sa.String(10), nullable=False),
        sa.Column("total_cost_usd", sa.Numeric(12, 8), nullable=False),
        sa.Column("total_tokens", sa.BigInteger(), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("date", "environment"),
    )
    op.create_index(
        "ix_daily_cost_rollups_date", "daily_cost_rollups", ["date"]
    )

    # ── model_cost_rollups ──────────────────────────────────
    op.create_table(
        "model_cost_rollups",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("environment", sa.String(10), nullable=False),
        sa.Column("total_cost_usd", sa.Numeric(12, 8), nullable=False),
        sa.Column("total_tokens", sa.BigInteger(), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("date", "model_name", "environment"),
    )
    op.create_index(
        "ix_model_cost_rollups_date", "model_cost_rollups", ["date"]
    )

    # ── endpoint_cost_rollups ───────────────────────────────
    op.create_table(
        "endpoint_cost_rollups",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("endpoint", sa.String(255), nullable=False),
        sa.Column("environment", sa.String(10), nullable=False),
        sa.Column("total_cost_usd", sa.Numeric(12, 8), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("date", "endpoint", "environment"),
    )
    op.create_index(
        "ix_endpoint_cost_rollups_date", "endpoint_cost_rollups", ["date"]
    )


def downgrade() -> None:
    op.drop_index("ix_endpoint_cost_rollups_date", table_name="endpoint_cost_rollups")
    op.drop_table("endpoint_cost_rollups")
    op.drop_index("ix_model_cost_rollups_date", table_name="model_cost_rollups")
    op.drop_table("model_cost_rollups")
    op.drop_index("ix_daily_cost_rollups_date", table_name="daily_cost_rollups")
    op.drop_table("daily_cost_rollups")
