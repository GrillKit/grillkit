# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Create coding_sections, coding_tasks, and code_run_attempts tables."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260609_0008"
down_revision: str | None = "20260608_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create coding section tables."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    if "coding_sections" not in existing:
        op.create_table(
            "coding_sections",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("interview_id", sa.String(), nullable=False),
            sa.Column("selection_spec", sa.Text(), nullable=False),
            sa.Column("question_count", sa.Integer(), nullable=False),
            sa.Column("task_time_limit_seconds", sa.Integer(), nullable=True),
            sa.Column(
                "status",
                sa.String(),
                server_default="active",
                nullable=False,
            ),
            sa.Column("section_score", sa.Integer(), nullable=True),
            sa.Column("section_feedback", sa.Text(), nullable=True),
            sa.Column(
                "locale",
                sa.String(),
                server_default="en",
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["interview_id"],
                ["interviews.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("interview_id"),
        )

    if "coding_tasks" not in existing:
        op.create_table(
            "coding_tasks",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("coding_section_id", sa.Integer(), nullable=False),
            sa.Column("question_id", sa.String(), nullable=False),
            sa.Column("order", sa.Integer(), nullable=False),
            sa.Column("round", sa.Integer(), server_default="0", nullable=False),
            sa.Column("question_text", sa.Text(), nullable=False),
            sa.Column("task_spec", sa.Text(), nullable=False),
            sa.Column("submitted_code", sa.Text(), nullable=True),
            sa.Column("submit_test_summary", sa.Text(), nullable=True),
            sa.Column("score", sa.Integer(), nullable=True),
            sa.Column("feedback", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["coding_section_id"],
                ["coding_sections.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    if "code_run_attempts" not in existing:
        op.create_table(
            "code_run_attempts",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("coding_task_id", sa.Integer(), nullable=False),
            sa.Column("attempt_no", sa.Integer(), nullable=True),
            sa.Column("source_code", sa.Text(), nullable=False),
            sa.Column("language", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("stdout", sa.Text(), nullable=True),
            sa.Column("stderr", sa.Text(), nullable=True),
            sa.Column("compile_output", sa.Text(), nullable=True),
            sa.Column("tests_passed", sa.Integer(), nullable=True),
            sa.Column("tests_total", sa.Integer(), nullable=True),
            sa.Column("test_results", sa.Text(), nullable=True),
            sa.Column("duration_ms", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["coding_task_id"],
                ["coding_tasks.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )


def downgrade() -> None:
    """Drop coding section tables."""
    op.drop_table("code_run_attempts")
    op.drop_table("coding_tasks")
    op.drop_table("coding_sections")
