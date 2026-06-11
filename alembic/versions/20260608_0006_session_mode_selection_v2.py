# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Add session_mode and migrate selection_spec to v2."""

from collections.abc import Sequence
import json

import sqlalchemy as sa

from alembic import op

revision: str = "20260608_0006"
down_revision: str | None = "20260608_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SESSION_SPEC_VERSION = 2


def _is_v2(data: dict[str, object]) -> bool:
    """Return whether a parsed selection_spec payload is already v2."""
    return data.get("version") == SESSION_SPEC_VERSION or (
        "session_mode" in data and "theory" in data
    )


def _v1_to_v2(
    data: dict[str, object],
    *,
    question_count: int,
    task_time_limit_seconds: int | None,
) -> dict[str, object]:
    """Convert a legacy v1 selection_spec payload to v2."""
    sources = data.get("sources", [])
    if not isinstance(sources, list):
        sources = []
    return {
        "version": SESSION_SPEC_VERSION,
        "session_mode": "theory_only",
        "theory": {
            "enabled": True,
            "question_count": question_count,
            "task_time_limit_seconds": task_time_limit_seconds,
            "sources": sources,
        },
        "coding": {
            "enabled": False,
            "question_count": 0,
            "task_time_limit_seconds": None,
            "sources": [],
        },
    }


def upgrade() -> None:
    """Add session_mode and backfill selection_spec v2 for existing interviews."""
    op.add_column(
        "interviews",
        sa.Column(
            "session_mode",
            sa.String(),
            nullable=False,
            server_default="theory_only",
        ),
    )

    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT id, selection_spec, question_count, question_time_limit_seconds "
            "FROM interviews"
        )
    ).fetchall()

    for interview_id, raw, question_count, timer in rows:
        if not raw:
            continue
        data = json.loads(raw)
        if not isinstance(data, dict):
            continue
        if _is_v2(data):
            session_mode = data.get("session_mode", "theory_only")
            spec = raw
        else:
            session_mode = "theory_only"
            spec = json.dumps(
                _v1_to_v2(
                    data,
                    question_count=int(question_count or 5),
                    task_time_limit_seconds=timer,
                ),
                separators=(",", ":"),
            )
        conn.execute(
            sa.text(
                "UPDATE interviews SET selection_spec = :spec, session_mode = :mode "
                "WHERE id = :id"
            ),
            {"spec": spec, "mode": session_mode, "id": interview_id},
        )


def downgrade() -> None:
    """Drop session_mode and flatten v2 selection_spec rows to v1 sources."""
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, selection_spec FROM interviews")).fetchall()

    for interview_id, raw in rows:
        if not raw:
            continue
        data = json.loads(raw)
        if not isinstance(data, dict) or not _is_v2(data):
            continue
        theory = data.get("theory")
        if not isinstance(theory, dict):
            continue
        sources = theory.get("sources", [])
        if not isinstance(sources, list):
            sources = []
        spec = json.dumps({"sources": sources}, separators=(",", ":"))
        conn.execute(
            sa.text("UPDATE interviews SET selection_spec = :spec WHERE id = :id"),
            {"spec": spec, "id": interview_id},
        )

    op.drop_column("interviews", "session_mode")
