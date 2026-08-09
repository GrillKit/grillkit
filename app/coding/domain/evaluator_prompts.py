# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Prompt templates for coding AI evaluation."""

import json
from typing import Any

CODING_ANSWER_EVALUATION_INSTRUCTIONS = """You are a technical interviewer evaluating a coding submission.
Use the task prompt, submitted code, optional Run attempt history, hidden test results,
and expected rubric points.

Scoring guide:
- 5: Excellent — correct, clean, demonstrates strong understanding
- 4: Good — solid solution with minor issues
- 3: Adequate — partially correct or shallow understanding
- 2: Weak — significant gaps or major issues
- 1: Poor — incorrect or empty submission

If hidden tests failed, cap the score at 3 and set follow_up_needed to true.
If the candidate made no Run attempts, note that as a weakness but do not block scoring.
If Run attempts show repeated compile errors or failing tests, lower the score and prefer follow-up.

When follow_up_needed is true, set follow_up_mode:
- "code" when the candidate should fix or extend code in the editor
- "explanation" when the candidate should explain their approach in text

Do not set follow_up_needed when the answer is already strong (score 4-5) unless hidden tests failed."""

CODING_SECTION_EVALUATION_INSTRUCTIONS = """You are a technical interviewer providing a coding section evaluation.
Review all coding task submissions from this section and provide:
1. Section narrative feedback summarizing performance in this coding section only
2. Topics they should review based on this section
3. Key strengths demonstrated in this section
4. A per-task score breakdown for this section

For score_breakdown, use task IDs as keys. Each value is an object
with "score" (sum of all rounds for that task) and "max" fields.

Return a JSON data object with your evaluation content. Do NOT return JSON Schema
metadata or a schema description — only the evaluation data object itself."""

CODING_FOLLOW_UP_EVALUATION_INSTRUCTIONS = """You are a technical interviewer evaluating a coding follow-up round.
Review the original task, initial submission, follow-up prompt, and the follow-up response code.

Score 1-5 using the same guide as the initial coding evaluation.
If the follow-up scores 2 or below and this is not the final allowed follow-up round,
you may request another follow-up with an appropriate follow_up_mode."""


def format_run_attempts(run_attempts: tuple[dict[str, Any], ...]) -> str:
    """Serialize Run attempt history for evaluator prompts.

    Args:
        run_attempts: Persisted attempt payloads for the task.

    Returns:
        Human-readable summary text.
    """
    if not run_attempts:
        return "No Run attempts were recorded before submit."
    lines: list[str] = []
    for attempt in run_attempts:
        lines.append(
            f"Attempt #{attempt.get('attempt_no', '?')}: "
            f"status={attempt.get('status')}, "
            f"tests={attempt.get('tests_passed')}/{attempt.get('tests_total')}"
        )
        if attempt.get("compile_output"):
            lines.append(f"  compile_output: {attempt['compile_output']}")
        if attempt.get("stderr"):
            lines.append(f"  stderr: {attempt['stderr']}")
    return "\n".join(lines)


def format_submit_test_summary(summary: dict[str, Any] | None) -> str:
    """Serialize hidden test results for evaluator prompts.

    Args:
        summary: Hidden test summary persisted on submit.

    Returns:
        Human-readable summary text.
    """
    if summary is None:
        return "Hidden tests were not executed for this task."
    return json.dumps(summary, indent=2, ensure_ascii=False)


def build_coding_evaluation_user_text(
    *,
    prompt_text: str,
    source_code: str,
    expected_points: list[str],
    run_attempts: tuple[dict[str, Any], ...],
    submit_test_summary: dict[str, Any] | None,
    initial_prompt_text: str | None = None,
    initial_source_code: str | None = None,
    follow_up_prompt: str | None = None,
) -> str:
    """Build the user message for a coding evaluation request.

    Args:
        prompt_text: Task or follow-up prompt shown to the candidate.
        source_code: Submitted source code for the evaluated round.
        expected_points: Rubric bullets from the task bank.
        run_attempts: Run attempt history before submit.
        submit_test_summary: Hidden test summary from submit.
        initial_prompt_text: Original task prompt for follow-up rounds.
        initial_source_code: Initial submitted code for follow-up rounds.
        follow_up_prompt: Follow-up prompt for follow-up round evaluation.

    Returns:
        User message text for the LLM.
    """
    rubric = "\n".join(f"- {point}" for point in expected_points) or "(none)"
    sections = [
        f"Task prompt:\n{prompt_text}",
        f"Submitted code:\n{source_code}",
        f"Expected rubric points:\n{rubric}",
        f"Run attempts:\n{format_run_attempts(run_attempts)}",
        f"Hidden test summary:\n{format_submit_test_summary(submit_test_summary)}",
    ]
    if initial_prompt_text is not None:
        sections.insert(0, f"Original task prompt:\n{initial_prompt_text}")
    if initial_source_code is not None:
        sections.insert(2, f"Initial submitted code:\n{initial_source_code}")
    if follow_up_prompt is not None:
        sections.insert(-2, f"Follow-up prompt:\n{follow_up_prompt}")
    return "\n\n".join(sections)
