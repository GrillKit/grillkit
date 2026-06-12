# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Tests for Python Judge0 harness generation."""

from app.coding.services.harness import build_python_script


def test_build_python_script_script_mode() -> None:
    """Script mode wraps bare code with a main guard when needed."""
    script = build_python_script("x = 1\nprint(x)", entrypoint=None)
    assert "print(x)" in script
    assert "__main__" in script


def test_build_python_script_entrypoint_invokes_callable() -> None:
    """Entrypoint mode parses stdin lines and calls the named function."""
    source = "def add(a, b):\n    return a + b"
    script = build_python_script(
        source,
        entrypoint="add",
        stdin="1\n2\n",
    )
    assert "def add(a, b):" in script
    assert "__grillkit_invoke" in script
    assert "'add'(*args)" in script
