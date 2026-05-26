# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Remove obsolete version field from selection_spec JSON."""

from collections.abc import Sequence
import json

import sqlalchemy as sa

from alembic import op

revision: str = "20260526_0003"
down_revision: str | None = "20260526_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Drop ``version`` from stored selection_spec payloads."""
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, selection_spec FROM interviews")).fetchall()
    for interview_id, raw in rows:
        if not raw:
            continue
        data = json.loads(raw)
        if not isinstance(data, dict) or "version" not in data:
            continue
        data.pop("version", None)
        conn.execute(
            sa.text("UPDATE interviews SET selection_spec = :spec WHERE id = :id"),
            {
                "spec": json.dumps(data, separators=(",", ":")),
                "id": interview_id,
            },
        )


def downgrade() -> None:
    """Restore ``version``: 1 on selection_spec payloads."""
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, selection_spec FROM interviews")).fetchall()
    for interview_id, raw in rows:
        if not raw:
            continue
        data = json.loads(raw)
        if not isinstance(data, dict):
            continue
        if data.get("version") == 1:
            continue
        data["version"] = 1
        conn.execute(
            sa.text("UPDATE interviews SET selection_spec = :spec WHERE id = :id"),
            {
                "spec": json.dumps(data, separators=(",", ":")),
                "id": interview_id,
            },
        )
