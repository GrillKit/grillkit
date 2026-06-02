# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""Interview aggregate entities."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from app.interview.domain.exceptions import (
    AnswerNotFoundError,
    InterviewNotActiveError,
    UnansweredAnswerNotFoundError,
)
from app.interview.domain.value_objects import InterviewSelection
from app.questions import Question
from app.shared.locales import TIMEOUT_FEEDBACK_MESSAGES, localized_string

InterviewStatus = Literal["active", "completed"]


@dataclass(frozen=True, slots=True)
class Answer:
    """One answer round within an interview session.

    Attributes:
        id: Answer row primary key.
        interview_id: Parent interview UUID.
        question_id: YAML question ID.
        order: Display order within the session (1-based).
        round: Follow-up round number (0 = initial).
        question_text: Question text shown to the user.
        question_code: Optional code snippet for the question.
        answer_text: User answer text, or None when unanswered.
        score: AI score for the round, or None when not evaluated.
        feedback: AI-generated feedback text, or None.
        started_at: When the round timer started, or None.
        created_at: When this answer row was created.
    """

    TIME_EXPIRED_ANSWER_TEXT = "[Time expired]"
    TIMEOUT_GRACE_SECONDS = 2
    NEW_ID = 0

    id: int
    interview_id: str
    question_id: str
    order: int
    round: int
    question_text: str
    question_code: str | None
    answer_text: str | None
    score: int | None
    feedback: str | None
    started_at: datetime | None
    created_at: datetime

    def timer_deadline(self, limit_seconds: int) -> datetime:
        """Compute the absolute deadline for this timed answer round.

        Args:
            limit_seconds: Allowed duration in seconds.

        Returns:
            Timezone-aware deadline timestamp.

        Raises:
            ValueError: If the round has no ``started_at`` timestamp.
        """
        if self.started_at is None:
            raise ValueError("Answer round has no started_at")
        started_at = self.started_at
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=UTC)
        return started_at + timedelta(seconds=limit_seconds)

    def is_timer_expired(
        self,
        limit_seconds: int | None,
        now: datetime | None = None,
        *,
        grace_seconds: int = TIMEOUT_GRACE_SECONDS,
    ) -> bool:
        """Return whether the per-round timer has elapsed.

        Args:
            limit_seconds: Configured limit for the session (None disables timer).
            now: Current time (defaults to UTC now).
            grace_seconds: Extra seconds allowed for network delay on timeout submit.

        Returns:
            True if the timer is enabled and the deadline plus grace has passed.
        """
        if limit_seconds is None or self.started_at is None:
            return False
        if now is None:
            now = datetime.now(UTC)
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)
        return now >= self.timer_deadline(limit_seconds) + timedelta(
            seconds=grace_seconds
        )

    def remaining_seconds(
        self,
        limit_seconds: int | None,
        now: datetime | None = None,
    ) -> int | None:
        """Return whole seconds left on the timer, or None if disabled.

        Args:
            limit_seconds: Configured limit for the session.
            now: Current time (defaults to UTC now).

        Returns:
            Non-negative seconds remaining, or None when the timer is off.
        """
        if limit_seconds is None or self.started_at is None:
            return None
        if now is None:
            now = datetime.now(UTC)
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)
        end = self.timer_deadline(limit_seconds)
        delta = (end - now).total_seconds()
        return max(0, int(delta))

    def client_timeout_due(
        self,
        limit_seconds: int | None,
        now: datetime | None = None,
    ) -> bool:
        """Return whether a client-sent timeout should be accepted.

        Args:
            limit_seconds: Configured limit for the session.
            now: Current time (defaults to UTC now).

        Returns:
            True when the round timer has effectively expired for the client.
        """
        if limit_seconds is None or self.started_at is None:
            return False
        rem = self.remaining_seconds(limit_seconds, now)
        return self.is_timer_expired(limit_seconds, now, grace_seconds=0) or (
            rem is not None and rem <= 0
        )


@dataclass(frozen=True, slots=True)
class Interview:
    """Interview session aggregate root.

    Attributes:
        id: Interview UUID.
        locale: Language code for feedback and voice.
        selection: Parsed question-bank selection.
        question_count: Number of questions in this session.
        question_ids: Question IDs in display order.
        question_time_limit_seconds: Per-round time limit, or None when disabled.
        status: Session status (``active`` or ``completed``).
        score: Final session score when completed.
        overall_feedback: Parsed overall evaluation payload when completed.
        started_at: When the session began.
        completed_at: When the session ended, or None while active.
        answers: Answer rounds in display order (order, then round).
    """

    MAX_SCORE_PER_ROUND = 5

    id: str
    locale: str
    selection: InterviewSelection
    question_count: int
    question_ids: tuple[str, ...]
    question_time_limit_seconds: int | None
    status: InterviewStatus
    score: int | None
    overall_feedback: dict[str, Any] | None
    started_at: datetime
    completed_at: datetime | None
    answers: tuple[Answer, ...]

    @classmethod
    def start(
        cls,
        interview_id: str,
        *,
        selection: InterviewSelection,
        locale: str,
        planned_questions: tuple[Question, ...],
        question_time_limit_seconds: int | None = None,
        started_at: datetime | None = None,
    ) -> Interview:
        """Build a new active interview aggregate from a question plan.

        Args:
            interview_id: New session UUID.
            selection: Track/level/topic selection from setup.
            locale: Locale for AI feedback and follow-ups.
            planned_questions: Ordered questions for this session (non-empty).
            question_time_limit_seconds: Per-round time limit, or None to disable.
            started_at: Session start time (defaults to UTC now).

        Returns:
            Active aggregate with initial answer rows (``Answer.NEW_ID``).

        Raises:
            ValueError: If ``planned_questions`` is empty.
        """
        if not planned_questions:
            raise ValueError("No questions found for the selected topics")

        when = started_at or datetime.now(UTC)
        question_ids = tuple(question.id for question in planned_questions)
        timer_start = when if question_time_limit_seconds is not None else None
        answers: list[Answer] = []
        for order, question in enumerate(planned_questions, start=1):
            answers.append(
                Answer(
                    id=Answer.NEW_ID,
                    interview_id=interview_id,
                    question_id=question.id,
                    order=order,
                    round=0,
                    question_text=question.text,
                    question_code=question.code,
                    answer_text=None,
                    score=None,
                    feedback=None,
                    started_at=timer_start if order == 1 else None,
                    created_at=when,
                )
            )
        return cls(
            id=interview_id,
            locale=locale,
            selection=selection,
            question_count=len(planned_questions),
            question_ids=question_ids,
            question_time_limit_seconds=question_time_limit_seconds,
            status="active",
            score=None,
            overall_feedback=None,
            started_at=when,
            completed_at=None,
            answers=tuple(answers),
        )

    def ensure_active(self) -> None:
        """Ensure this interview accepts new answers.

        Raises:
            InterviewNotActiveError: If the interview is not in ``active`` status.
        """
        if self.status != "active":
            raise InterviewNotActiveError(self.id)

    def start_timer_for_answer(
        self, answer_id: int, when: datetime | None = None
    ) -> Interview:
        """Start the per-round timer on an answer when the session has a limit.

        Args:
            answer_id: Primary key of the answer row to activate.
            when: Timestamp to set (defaults to UTC now).

        Returns:
            A new aggregate with ``started_at`` set on the target answer when applicable.
        """
        if self.question_time_limit_seconds is None:
            return self
        started_at = when or datetime.now(UTC)
        answers = tuple(
            replace(answer, started_at=started_at)
            if answer.id == answer_id and answer.started_at is None
            else answer
            for answer in self.answers
        )
        return replace(self, answers=answers)

    def with_answer_text(self, answer_id: int, text: str) -> Interview:
        """Return aggregate with user answer text on the given row.

        Args:
            answer_id: Primary key of the answer row to update.
            text: User answer text (maybe empty before transcription).

        Returns:
            A new aggregate with ``answer_text`` set on the target answer.
        """
        answers = tuple(
            replace(answer, answer_text=text) if answer.id == answer_id else answer
            for answer in self.answers
        )
        return replace(self, answers=answers)

    def with_timed_out_round(self, answer_id: int, locale: str) -> Interview:
        """Return aggregate with a timed-out round scored zero.

        Args:
            answer_id: Primary key of the answer row that expired.
            locale: Interview locale for timeout feedback text.

        Returns:
            A new aggregate with timeout marker text, score 0, and feedback.
        """
        feedback = self.timeout_feedback(locale)
        answers = tuple(
            replace(
                answer,
                answer_text=Answer.TIME_EXPIRED_ANSWER_TEXT,
                score=0,
                feedback=feedback,
            )
            if answer.id == answer_id
            else answer
            for answer in self.answers
        )
        return replace(self, answers=answers)

    def with_evaluation(
        self, question_id: str, round_num: int, score: int, feedback: str
    ) -> Interview:
        """Return aggregate with AI score and feedback on one answer round.

        Args:
            question_id: YAML question ID.
            round_num: Follow-up round (0 = initial).
            score: AI score for the round.
            feedback: AI feedback text.

        Returns:
            A new aggregate with evaluation fields set on the target answer.
        """
        target = self.find_answer(question_id, round_num)
        answers = tuple(
            replace(answer, score=score, feedback=feedback)
            if answer.id == target.id
            else answer
            for answer in self.answers
        )
        return replace(self, answers=answers)

    def max_round_for_question(self, question_id: str) -> int:
        """Return the highest follow-up round number for a question.

        Args:
            question_id: YAML question ID.

        Returns:
            Maximum ``round`` value among answers for the question, or 0 when none exist.
        """
        rounds = [
            answer.round for answer in self.answers if answer.question_id == question_id
        ]
        return max(rounds) if rounds else 0

    def with_follow_up(
        self, question_id: str, question_text: str
    ) -> tuple[Interview, Answer]:
        """Return aggregate with a new unanswered follow-up answer row.

        Args:
            question_id: YAML question ID for the follow-up chain.
            question_text: Follow-up question text shown to the user.

        Returns:
            Tuple of updated aggregate and the pending follow-up answer (``id`` is ``NEW_ID``).
        """
        base = self.find_answer(question_id, 0)
        next_round = self.max_round_for_question(question_id) + 1
        created_at = datetime.now(UTC)
        follow_up = Answer(
            id=Answer.NEW_ID,
            interview_id=self.id,
            question_id=question_id,
            order=base.order,
            round=next_round,
            question_text=question_text,
            question_code=base.question_code,
            answer_text=None,
            score=None,
            feedback=None,
            started_at=None,
            created_at=created_at,
        )
        return replace(self, answers=self.answers + (follow_up,)), follow_up

    @staticmethod
    def timeout_feedback(locale: str) -> str:
        """Localized feedback text for a timed-out answer.

        Args:
            locale: Interview locale code (e.g. ``en``, ``ru``).

        Returns:
            Short feedback string shown to the user.
        """
        return localized_string(locale, TIMEOUT_FEEDBACK_MESSAGES)

    def find_first_unanswered(self) -> Answer | None:
        """Return the first unanswered answer in display order.

        Returns:
            The first answer with no ``answer_text``, or None.
        """
        for answer in self.answers:
            if answer.answer_text is None:
                return answer
        return None

    def find_unanswered_for_question(self, question_id: str) -> Answer:
        """Return the unanswered answer row for a question (any follow-up round).

        Args:
            question_id: YAML question ID.

        Returns:
            The first unanswered answer for that question.

        Raises:
            UnansweredAnswerNotFoundError: If no unanswered answer exists for the question.
        """
        for answer in self.answers:
            if answer.question_id == question_id and answer.answer_text is None:
                return answer
        raise UnansweredAnswerNotFoundError(self.id, question_id)

    def find_answer(self, question_id: str, round_num: int) -> Answer:
        """Return the answer row for a question and follow-up round.

        Args:
            question_id: YAML question ID.
            round_num: Follow-up round (0 = initial).

        Returns:
            The matching answer row.

        Raises:
            AnswerNotFoundError: If no row matches the keys.
        """
        for answer in self.answers:
            if answer.question_id == question_id and answer.round == round_num:
                return answer
        raise AnswerNotFoundError(self.id, question_id, round_num)

    def find_next_unanswered_after(self, current_index: int) -> Answer | None:
        """Return the next unanswered answer after a position in the answer list.

        Args:
            current_index: Index of the current answer in ``answers``.

        Returns:
            The next unanswered answer, or None if none remain.
        """
        for answer in self.answers[current_index + 1 :]:
            if answer.answer_text is None:
                return answer
        return None

    def total_score(self) -> int:
        """Sum scores from all answered rounds in this session.

        Returns:
            Total score, or 0 if no scored answers exist.
        """
        scores = [answer.score for answer in self.answers if answer.score is not None]
        return sum(scores) if scores else 0

    def per_question_score_breakdown(self) -> dict[str, Any]:
        """Aggregate earned and maximum scores per question from persisted answers.

        Returns:
            Mapping ``question_id`` → ``{"score": int, "max": int}`` for questions
            with at least one answered round.
        """
        rounds_by_question: defaultdict[str, list[Answer]] = defaultdict(list)
        for answer in self.answers:
            if answer.answer_text is not None:
                rounds_by_question[answer.question_id].append(answer)

        breakdown: dict[str, Any] = {}
        for question_id, rounds in rounds_by_question.items():
            earned = sum((r.score or 0) for r in rounds)
            maximum = self.MAX_SCORE_PER_ROUND * len(rounds)
            breakdown[question_id] = {"score": earned, "max": maximum}
        return breakdown

    def with_session_completed(
        self,
        overall_feedback: dict[str, Any],
        *,
        completed_at: datetime | None = None,
    ) -> Interview:
        """Return aggregate marked completed with final evaluation payload.

        Args:
            overall_feedback: Parsed overall evaluation dict for persistence.
            completed_at: Session end time (defaults to UTC now).

        Returns:
            A new aggregate with ``status`` completed, total score, and feedback set.
        """
        when = completed_at or datetime.now(UTC)
        return replace(
            self,
            status="completed",
            score=self.total_score(),
            overall_feedback=overall_feedback,
            completed_at=when,
        )

    def next_question_client_payload(self, answer: Answer) -> dict[str, Any]:
        """Build WebSocket/API payload for the next unanswered question.

        Args:
            answer: Next unanswered answer round.

        Returns:
            Dict with question fields for the client.
        """
        return {
            "question_id": answer.question_id,
            "order": answer.order,
            "question_text": answer.question_text,
            "question_code": answer.question_code,
            "round": answer.round,
        }
