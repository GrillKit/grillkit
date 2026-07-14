# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Add known_questions table for excluding marked questions from planning."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260615_0011"
down_revision: str | None = "20260612_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create known_questions table with composite primary key."""
    op.create_table(
        "known_questions",
        sa.Column("branch", sa.Text(), nullable=False),
        sa.Column("bank_item_id", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("branch", "bank_item_id"),
    )


def downgrade() -> None:
    """Drop known_questions table."""
    op.drop_table("known_questions")
