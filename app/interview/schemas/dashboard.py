# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Dashboard read models for interview history."""

from pydantic import BaseModel, ConfigDict


class DashboardRowRead(BaseModel):
    """Row model for the dashboard interview history table.

    Attributes:
        id: Interview UUID.
        title: Display title (e.g. "Python Interview").
        question_count: Number of questions in the session.
        score_display: Formatted score or em dash when not finished.
        status: Raw status ("active" or "completed").
        status_label: Human-readable status for the UI.
        datetime_display: Localized date/time string for the row.
        url: Link to the interview page.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    question_count: int
    score_display: str
    status: str
    status_label: str
    datetime_display: str
    url: str
