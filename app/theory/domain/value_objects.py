# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Theory domain value objects."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PlannedTheoryQuestion:
    """Question snapshot used when starting a theory section.

    Attributes:
        id: Unique question identifier from the question bank.
        text: Localized question text shown to the user.
        code: Optional code snippet, or None when not applicable.
        expected_points: Rubric bullets for AI evaluation.
    """

    id: str
    text: str
    code: str | None
    expected_points: tuple[str, ...] = ()
