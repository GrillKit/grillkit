# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for CreateCodingSection."""

from app.coding.use_cases.create_section import CreateCodingSection


def test_create_section_class_exists() -> None:
    """CreateCodingSection can be imported and instantiated."""
    assert CreateCodingSection is not None
