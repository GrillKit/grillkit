# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Wire models for known bank-item exclusion API."""

from pydantic import BaseModel, Field

from app.interview.domain.value_objects import SectionKind


class KnownItemMutation(BaseModel):
    """Request body for marking or unmarking a known bank item.

    Attributes:
        branch: Section branch (``theory`` or ``coding``).
        item_id: ID from the YAML bank for that branch.
    """

    branch: SectionKind
    item_id: str = Field(min_length=1)


class KnownItemsResponse(BaseModel):
    """Known bank item IDs grouped by section branch.

    Attributes:
        theory: Theory question IDs marked as known.
        coding: Coding task IDs marked as known.
    """

    theory: list[str]
    coding: list[str]
