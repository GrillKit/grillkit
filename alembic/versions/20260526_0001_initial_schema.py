# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Create initial interview schema."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260526_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create core tables when missing (existing installs may already have them)."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    if "interviews" not in existing:
        op.create_table(
            "interviews",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column(
                "locale",
                sa.String(),
                server_default="en",
                nullable=False,
            ),
            sa.Column("selection_spec", sa.Text(), nullable=False),
            sa.Column("question_count", sa.Integer(), nullable=False),
            sa.Column(
                "question_ids",
                sa.Text(),
                server_default="[]",
                nullable=False,
            ),
            sa.Column("question_time_limit_seconds", sa.Integer(), nullable=True),
            sa.Column(
                "status",
                sa.String(),
                server_default="active",
                nullable=False,
            ),
            sa.Column("score", sa.Integer(), nullable=True),
            sa.Column("overall_feedback", sa.Text(), nullable=True),
            sa.Column(
                "started_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
                nullable=False,
            ),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )

    if "answers" not in existing:
        op.create_table(
            "answers",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("interview_id", sa.String(), nullable=False),
            sa.Column("question_id", sa.String(), nullable=False),
            sa.Column("order", sa.Integer(), nullable=False),
            sa.Column("round", sa.Integer(), nullable=False),
            sa.Column("question_text", sa.Text(), nullable=False),
            sa.Column("question_code", sa.Text(), nullable=True),
            sa.Column("answer_text", sa.Text(), nullable=True),
            sa.Column("score", sa.Integer(), nullable=True),
            sa.Column("feedback", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["interview_id"],
                ["interviews.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )


def downgrade() -> None:
    """Drop core tables."""
    op.drop_table("answers")
    op.drop_table("interviews")
