# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Add expected_points rubric snapshot column to answers."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260612_0010"
down_revision: str | None = "20260610_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Store rubric bullets on each theory answer row."""
    with op.batch_alter_table("answers") as batch_op:
        batch_op.add_column(sa.Column("expected_points", sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove expected_points from answers."""
    with op.batch_alter_table("answers") as batch_op:
        batch_op.drop_column("expected_points")
