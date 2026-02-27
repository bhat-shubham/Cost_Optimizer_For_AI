"""add auth tables and project scoping

Revision ID: 0003
Revises: 0002
Create Date: 2026-02-27

Phase 3.1: API Authentication & Project-Level Isolation
  - Creates projects and api_keys tables
  - Adds project_id FK to usage_events
  - Recreates rollup tables with project_id in composite PKs
  - Old rollup data is dropped (rollups are derived and can be regenerated)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. projects table ───────────────────────────────────
    op.create_table(
        "projects",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── 2. api_keys table ───────────────────────────────────
    op.create_table(
        "api_keys",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("key_hash", sa.Text(), nullable=False),
        sa.Column("prefix", sa.String(12), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("key_hash"),
    )
    op.create_index("ix_api_keys_project_id", "api_keys", ["project_id"])
    op.create_index("ix_api_keys_key_hash", "api_keys", ["key_hash"])

    # ── 3. Add project_id to usage_events ───────────────────
    op.add_column(
        "usage_events",
        sa.Column("project_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_usage_events_project_id",
        "usage_events",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_usage_events_project_id", "usage_events", ["project_id"])

    # ── 4. Recreate rollup tables with project_id in PK ────
    #    Rollups are derived data — safe to drop and recreate.

    # Drop old rollup tables
    op.drop_index("ix_endpoint_cost_rollups_date", table_name="endpoint_cost_rollups")
    op.drop_table("endpoint_cost_rollups")
    op.drop_index("ix_model_cost_rollups_date", table_name="model_cost_rollups")
    op.drop_table("model_cost_rollups")
    op.drop_index("ix_daily_cost_rollups_date", table_name="daily_cost_rollups")
    op.drop_table("daily_cost_rollups")

    # Recreate with project_id in composite PK
    op.create_table(
        "daily_cost_rollups",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("environment", sa.String(10), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("total_cost_usd", sa.Numeric(12, 8), nullable=False),
        sa.Column("total_tokens", sa.BigInteger(), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("date", "environment", "project_id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_daily_cost_rollups_date", "daily_cost_rollups", ["date"])
    op.create_index("ix_daily_cost_rollups_project_id", "daily_cost_rollups", ["project_id"])

    op.create_table(
        "model_cost_rollups",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("environment", sa.String(10), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("total_cost_usd", sa.Numeric(12, 8), nullable=False),
        sa.Column("total_tokens", sa.BigInteger(), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("date", "model_name", "environment", "project_id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_model_cost_rollups_date", "model_cost_rollups", ["date"])
    op.create_index("ix_model_cost_rollups_project_id", "model_cost_rollups", ["project_id"])

    op.create_table(
        "endpoint_cost_rollups",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("endpoint", sa.String(255), nullable=False),
        sa.Column("environment", sa.String(10), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("total_cost_usd", sa.Numeric(12, 8), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("date", "endpoint", "environment", "project_id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_endpoint_cost_rollups_date", "endpoint_cost_rollups", ["date"])
    op.create_index("ix_endpoint_cost_rollups_project_id", "endpoint_cost_rollups", ["project_id"])


def downgrade() -> None:
    # Drop new rollup tables
    op.drop_index("ix_endpoint_cost_rollups_project_id", table_name="endpoint_cost_rollups")
    op.drop_index("ix_endpoint_cost_rollups_date", table_name="endpoint_cost_rollups")
    op.drop_table("endpoint_cost_rollups")
    op.drop_index("ix_model_cost_rollups_project_id", table_name="model_cost_rollups")
    op.drop_index("ix_model_cost_rollups_date", table_name="model_cost_rollups")
    op.drop_table("model_cost_rollups")
    op.drop_index("ix_daily_cost_rollups_project_id", table_name="daily_cost_rollups")
    op.drop_index("ix_daily_cost_rollups_date", table_name="daily_cost_rollups")
    op.drop_table("daily_cost_rollups")

    # Recreate old rollup tables without project_id
    op.create_table(
        "daily_cost_rollups",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("environment", sa.String(10), nullable=False),
        sa.Column("total_cost_usd", sa.Numeric(12, 8), nullable=False),
        sa.Column("total_tokens", sa.BigInteger(), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("date", "environment"),
    )
    op.create_index("ix_daily_cost_rollups_date", "daily_cost_rollups", ["date"])

    op.create_table(
        "model_cost_rollups",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("environment", sa.String(10), nullable=False),
        sa.Column("total_cost_usd", sa.Numeric(12, 8), nullable=False),
        sa.Column("total_tokens", sa.BigInteger(), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("date", "model_name", "environment"),
    )
    op.create_index("ix_model_cost_rollups_date", "model_cost_rollups", ["date"])

    op.create_table(
        "endpoint_cost_rollups",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("endpoint", sa.String(255), nullable=False),
        sa.Column("environment", sa.String(10), nullable=False),
        sa.Column("total_cost_usd", sa.Numeric(12, 8), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("date", "endpoint", "environment"),
    )
    op.create_index("ix_endpoint_cost_rollups_date", "endpoint_cost_rollups", ["date"])

    # Remove project_id from usage_events
    op.drop_index("ix_usage_events_project_id", table_name="usage_events")
    op.drop_constraint("fk_usage_events_project_id", "usage_events", type_="foreignkey")
    op.drop_column("usage_events", "project_id")

    # Drop auth tables
    op.drop_index("ix_api_keys_key_hash", table_name="api_keys")
    op.drop_index("ix_api_keys_project_id", table_name="api_keys")
    op.drop_table("api_keys")
    op.drop_table("projects")
