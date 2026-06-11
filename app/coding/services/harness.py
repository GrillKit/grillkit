# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Generate single-file Python scripts for Judge0 execution."""

from __future__ import annotations

import textwrap


def build_python_script(
    source_code: str,
    *,
    entrypoint: str | None,
    stdin: str = "",
) -> str:
    """Wrap candidate code for Judge0 execution.

    When ``entrypoint`` is set, stdin lines are parsed with ``ast.literal_eval``
    when possible and passed as positional arguments to the callable. Otherwise
    the candidate source is executed as a standalone script.

    Args:
        source_code: Candidate editor contents.
        entrypoint: Callable name to invoke, or None for script mode.
        stdin: Standard input fed to the submission.

    Returns:
        Full Python source sent to Judge0.
    """
    body = textwrap.dedent(source_code).strip("\n")
    if not entrypoint:
        if "__main__" in body:
            return f"{body}\n"
        return f"{body}\n\nif __name__ == '__main__':\n    pass\n"

    stdin_repr = repr(stdin)
    entrypoint_repr = repr(entrypoint)
    runner = f"""
import ast
import sys

{body}


def __grillkit_invoke():
    raw = {stdin_repr} if {stdin_repr} else sys.stdin.read()
    lines = [line for line in raw.splitlines() if line.strip()]
    if not lines:
        args = []
    else:
        args = []
        for line in lines:
            try:
                args.append(ast.literal_eval(line))
            except (ValueError, SyntaxError):
                args.append(line)
    result = {entrypoint_repr}(*args)
    if result is not None:
        print(result)


if __name__ == "__main__":
    __grillkit_invoke()
"""
    return textwrap.dedent(runner).strip() + "\n"
