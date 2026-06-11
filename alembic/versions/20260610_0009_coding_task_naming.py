# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Rename coding section columns to task-oriented names."""

from collections.abc import Sequence

from alembic import op

revision: str = "20260610_0009"
down_revision: str | None = "20260609_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Rename question_* columns on coding tables to task_* / prompt_text."""
    with op.batch_alter_table("coding_sections") as batch_op:
        batch_op.alter_column("question_count", new_column_name="task_count")

    with op.batch_alter_table("coding_tasks") as batch_op:
        batch_op.alter_column("question_id", new_column_name="task_id")
        batch_op.alter_column("question_text", new_column_name="prompt_text")


def downgrade() -> None:
    """Restore legacy question_* column names on coding tables."""
    with op.batch_alter_table("coding_tasks") as batch_op:
        batch_op.alter_column("prompt_text", new_column_name="question_text")
        batch_op.alter_column("task_id", new_column_name="question_id")

    with op.batch_alter_table("coding_sections") as batch_op:
        batch_op.alter_column("task_count", new_column_name="question_count")
