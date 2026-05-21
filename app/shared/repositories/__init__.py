# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Shared repository abstractions."""

from app.shared.repositories.base import Repository, SqlAlchemyRepository

__all__ = ["Repository", "SqlAlchemyRepository"]
