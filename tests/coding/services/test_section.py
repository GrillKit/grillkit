# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for CodingSectionService interview section protocol."""

from app.coding.services.section import CodingSectionService
from app.shared.infrastructure.models import Interview
from tests.helpers.coding_seed import (
    attach_coding_tasks,
    create_coding_section_for_interview,
)
from tests.helpers.selection import minimal_selection_spec


def test_coding_section_service_reports_incomplete_until_submitted(
    isolated_db,
) -> None:
    """Section protocol marks coding incomplete while tasks lack submissions."""
    del isolated_db
    interview_id = "coding-svc-1"
    interview = Interview(
        id=interview_id,
        selection_spec=minimal_selection_spec(),
        status="active",
    )
    from app.coding.repositories.uow import CodingUnitOfWork

    with CodingUnitOfWork() as uow:
        uow.session.add(interview)
        uow.commit()
        section = create_coding_section_for_interview(uow.session, interview)
        attach_coding_tasks(uow.session, section)
        uow.commit()

    assert CodingSectionService.is_complete(interview_id) is False
    context = CodingSectionService.get_page_context(interview_id)
    assert context is not None
    assert context.section == "coding"
    assert context.active is True
    assert context.complete is False
