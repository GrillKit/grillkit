# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Rename selection_spec source key from language to track."""

from collections.abc import Sequence
import json

import sqlalchemy as sa

from alembic import op

revision: str = "20260526_0002"
down_revision: str | None = "20260526_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _rename_key(raw: str, *, from_key: str, to_key: str) -> str | None:
    """Return updated JSON when any source uses ``from_key`` instead of ``to_key``."""
    if not raw:
        return None
    data = json.loads(raw)
    if not isinstance(data, dict):
        return None
    sources = data.get("sources")
    if not isinstance(sources, list):
        return None
    changed = False
    for item in sources:
        if not isinstance(item, dict):
            continue
        if from_key in item and to_key not in item:
            item[to_key] = item.pop(from_key)
            changed = True
        elif from_key in item and to_key in item:
            item.pop(from_key)
            changed = True
    if not changed:
        return None
    return json.dumps(data, separators=(",", ":"))


def upgrade() -> None:
    """Rewrite stored selection_spec JSON: language → track."""
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, selection_spec FROM interviews")).fetchall()
    for interview_id, raw in rows:
        updated = _rename_key(raw, from_key="language", to_key="track")
        if updated is None:
            continue
        conn.execute(
            sa.text("UPDATE interviews SET selection_spec = :spec WHERE id = :id"),
            {"spec": updated, "id": interview_id},
        )


def downgrade() -> None:
    """Restore selection_spec JSON: track → language."""
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, selection_spec FROM interviews")).fetchall()
    for interview_id, raw in rows:
        updated = _rename_key(raw, from_key="track", to_key="language")
        if updated is None:
            continue
        conn.execute(
            sa.text("UPDATE interviews SET selection_spec = :spec WHERE id = :id"),
            {"spec": updated, "id": interview_id},
        )
