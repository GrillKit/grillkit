# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Coding section page read models."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CodingPageContext(BaseModel):
    """Template context for the coding section panel.

    Attributes:
        task_count: Total coding tasks in the section.
        completed_tasks: Number of submitted tasks.
        current_task: Active unsubmitted task metadata for the editor.
        current_task_row_id: Primary key of the active task row.
        task_timer_enabled: Whether the per-task timer is active.
        task_time_limit_seconds: Configured limit in seconds.
        timer_remaining_seconds: Seconds left on the current task.
        current_round: Follow-up round number for the active task.
        complete: Whether all coding tasks have been submitted.
        section_status: Coding section status slug.
    """

    model_config = ConfigDict(frozen=True)

    task_count: int
    completed_tasks: int
    current_task: dict[str, Any] | None
    current_task_row_id: int | None
    task_timer_enabled: bool
    task_time_limit_seconds: int | None
    timer_remaining_seconds: int | None
    current_round: int = Field(default=0)
    complete: bool = False
    section_status: str = "active"
