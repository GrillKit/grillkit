# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for theory question planning."""

from pathlib import Path

import yaml

from app.interview.domain.value_objects import InterviewSelection, TrackSelection
from app.theory.services.planning import build_theory_question_plan


def test_build_theory_question_plan_from_theory_bank(temp_questions_dir) -> None:
    """Theory planning loads questions from the theory bank only."""
    del temp_questions_dir
    selection = InterviewSelection(
        sources=(
            TrackSelection(
                track="python",
                level="junior",
                categories=("data-structures",),
            ),
        )
    )
    planned = build_theory_question_plan(selection, question_count=1, locale="en")
    assert len(planned) == 1
    assert planned[0].id == "ds-001"


def test_build_theory_question_plan_skips_coding_type_rows(
    temp_questions_dir: Path,
) -> None:
    """Theory planning ignores legacy ``type: coding`` rows in the theory bank."""
    category_path = temp_questions_dir / "python" / "junior" / "mixed.yaml"
    category_path.parent.mkdir(parents=True, exist_ok=True)
    with open(category_path, "w") as f:
        yaml.dump(
            {
                "category": "Mixed",
                "track": "python",
                "level": "junior",
                "questions": [
                    {
                        "id": "theory-001",
                        "type": "knowledge",
                        "difficulty": 1,
                        "question": {"text": "Theory question"},
                    },
                    {
                        "id": "coding-001",
                        "type": "coding",
                        "difficulty": 2,
                        "question": {"text": "Coding question"},
                    },
                ],
            },
            f,
        )

    selection = InterviewSelection(
        sources=(
            TrackSelection(
                track="python",
                level="junior",
                categories=("mixed",),
            ),
        )
    )
    planned = build_theory_question_plan(selection, question_count=1, locale="en")
    assert len(planned) == 1
    assert planned[0].id == "theory-001"


def test_build_theory_question_plan_excludes_known_ids(
    temp_questions_dir: Path,
) -> None:
    """Theory planning omits excluded question IDs from the result."""
    category_path = temp_questions_dir / "python" / "junior" / "data-structures.yaml"
    with open(category_path) as handle:
        content = yaml.safe_load(handle)
    content["questions"].append(
        {
            "id": "ds-002",
            "type": "knowledge",
            "difficulty": 1,
            "question": {"text": "Second question", "code": None},
        }
    )
    with open(category_path, "w") as handle:
        yaml.dump(content, handle)

    selection = InterviewSelection(
        sources=(
            TrackSelection(
                track="python",
                level="junior",
                categories=("data-structures",),
            ),
        )
    )
    planned = build_theory_question_plan(
        selection,
        question_count=1,
        locale="en",
        excluded_ids=frozenset({"ds-001"}),
    )
    assert len(planned) == 1
    assert planned[0].id == "ds-002"
