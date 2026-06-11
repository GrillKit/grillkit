# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Add theory_section_id to answers and backfill from theory_sections."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260608_0005"
down_revision: str | None = "20260608_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Link each answer row to its parent theory section."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("answers")}

    if "theory_section_id" not in columns:
        with op.batch_alter_table("answers") as batch_op:
            batch_op.add_column(
                sa.Column("theory_section_id", sa.Integer(), nullable=True)
            )
            batch_op.create_foreign_key(
                "fk_answers_theory_section_id",
                "theory_sections",
                ["theory_section_id"],
                ["id"],
                ondelete="CASCADE",
            )

    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE answers
            SET theory_section_id = (
                SELECT ts.id
                FROM theory_sections ts
                WHERE ts.interview_id = answers.interview_id
            )
            WHERE theory_section_id IS NULL
            """
        )
    )

    with op.batch_alter_table("answers") as batch_op:
        batch_op.alter_column("theory_section_id", nullable=False)


def downgrade() -> None:
    """Remove theory_section_id from answers."""
    with op.batch_alter_table("answers") as batch_op:
        batch_op.drop_constraint("fk_answers_theory_section_id", type_="foreignkey")
        batch_op.drop_column("theory_section_id")
