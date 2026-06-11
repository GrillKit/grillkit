# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Create theory_sections table and backfill from interviews."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260608_0004"
down_revision: str | None = "20260526_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create ``theory_sections`` and backfill one row per existing interview."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    if "theory_sections" not in existing:
        op.create_table(
            "theory_sections",
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

    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            INSERT INTO theory_sections (
                interview_id,
                selection_spec,
                question_count,
                task_time_limit_seconds,
                status,
                locale
            )
            SELECT
                id,
                selection_spec,
                question_count,
                question_time_limit_seconds,
                CASE WHEN status = 'completed' THEN 'completed' ELSE 'active' END,
                COALESCE(locale, 'en')
            FROM interviews
            WHERE id NOT IN (SELECT interview_id FROM theory_sections)
            """
        )
    )


def downgrade() -> None:
    """Drop ``theory_sections``."""
    op.drop_table("theory_sections")
