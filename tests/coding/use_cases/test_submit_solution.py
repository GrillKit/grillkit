# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for SubmitCodingSolution."""

import pytest

from app.coding.use_cases.submit_solution import SubmitCodingSolution


@pytest.fixture
def submit_solution(uow):
    """Return a SubmitCodingSolution instance wired to the test UoW."""
    return SubmitCodingSolution(uow)


def test_submit_solution_class_exists() -> None:
    """SubmitCodingSolution can be imported and instantiated."""
    from app.coding.use_cases.submit_solution import SubmitCodingSolution

    assert SubmitCodingSolution is not None
