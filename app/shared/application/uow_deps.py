# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""FastAPI dependencies for application Unit of Work lifecycle."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends

from app.interview.repositories.uow import InterviewUnitOfWork


def get_uow() -> Iterator[InterviewUnitOfWork]:
    """Yield an application Unit of Work for the request scope.

    Yields:
        Active ``InterviewUnitOfWork``; commits are explicit unless auto-commit.
    """
    with InterviewUnitOfWork() as uow:
        yield uow


def get_uow_auto_commit() -> Iterator[InterviewUnitOfWork]:
    """Yield an application Unit of Work that commits on successful exit.

    Yields:
        Active ``InterviewUnitOfWork`` with ``auto_commit=True``.
    """
    with InterviewUnitOfWork(auto_commit=True) as uow:
        yield uow


UoWDep = Annotated[InterviewUnitOfWork, Depends(get_uow)]
UoWAutoCommitDep = Annotated[InterviewUnitOfWork, Depends(get_uow_auto_commit)]
