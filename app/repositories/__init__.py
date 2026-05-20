# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Abstract repository interfaces and SQLAlchemy implementations.

This package provides a repository abstraction layer over the database,
allowing the service layer to remain decoupled from the specific ORM.
"""

from app.repositories.answer import AnswerRepository
from app.repositories.base import Repository
from app.repositories.interview import InterviewRepository

__all__ = [
    "Repository",
    "InterviewRepository",
    "AnswerRepository",
]
