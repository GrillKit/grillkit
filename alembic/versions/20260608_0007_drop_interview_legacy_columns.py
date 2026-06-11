# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Drop legacy question/score columns from interviews and interview_id from answers."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260608_0007"
down_revision: str | None = "20260608_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INTERVIEW_LEGACY_COLUMNS = (
    "question_count",
    "question_ids",
    "question_time_limit_seconds",
    "score",
)


def upgrade() -> None:
    """Remove duplicated interview columns and answers.interview_id."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    interview_columns = {col["name"] for col in inspector.get_columns("interviews")}
    answer_columns = {col["name"] for col in inspector.get_columns("answers")}

    for column in _INTERVIEW_LEGACY_COLUMNS:
        if column in interview_columns:
            with op.batch_alter_table("interviews") as batch_op:
                batch_op.drop_column(column)

    if "interview_id" in answer_columns:
        for fk in inspector.get_foreign_keys("answers"):
            if "interview_id" in fk.get("constrained_columns", []):
                fk_name = fk.get("name")
                if fk_name:
                    with op.batch_alter_table("answers") as batch_op:
                        batch_op.drop_constraint(fk_name, type_="foreignkey")
        with op.batch_alter_table("answers") as batch_op:
            batch_op.drop_column("interview_id")


def downgrade() -> None:
    """Restore legacy interview and answer columns."""
    with op.batch_alter_table("interviews") as batch_op:
        batch_op.add_column(sa.Column("question_count", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("question_ids", sa.Text(), nullable=True, server_default="[]")
        )
        batch_op.add_column(
            sa.Column("question_time_limit_seconds", sa.Integer(), nullable=True)
        )
        batch_op.add_column(sa.Column("score", sa.Integer(), nullable=True))

    with op.batch_alter_table("answers") as batch_op:
        batch_op.add_column(sa.Column("interview_id", sa.String(), nullable=True))
        batch_op.create_foreign_key(
            "answers_interview_id_fkey",
            "interviews",
            ["interview_id"],
            ["id"],
            ondelete="CASCADE",
        )
