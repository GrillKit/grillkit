# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""SQLAlchemy models for GrillKit.

This module defines all database models, including interview sessions,
theory tasks, and future entities.
"""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.infrastructure.database import Base


class Interview(Base):
    """Interview session shell record.

    Stores top-level session metadata. Theory tasks live on ``theory_sections``.

    Attributes:
        id: Unique interview identifier (UUID v4).
        locale: Language for AI feedback and follow-ups (e.g., "en", "ru").
        selection_spec: JSON describing session mode and section branches (v2).
        session_mode: Session mode (theory_only, coding_only, or combined order).
        status: Interview status ("active", "completed").
        overall_feedback: JSON string with final evaluation feedback (None if not evaluated).
        started_at: Timestamp when interview began.
        completed_at: Timestamp when interview ended (None if active).
        theory_section: Optional theory section for this session.
    """

    __tablename__ = "interviews"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    locale: Mapped[str] = mapped_column(String, default="en", server_default="en")
    selection_spec: Mapped[str] = mapped_column(Text)
    session_mode: Mapped[str] = mapped_column(
        String, default="theory_only", server_default="theory_only"
    )
    status: Mapped[str] = mapped_column(String, default="active")
    overall_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    theory_section: Mapped["TheorySection | None"] = relationship(
        "TheorySection",
        back_populates="interview",
        uselist=False,
        cascade="all, delete-orphan",
    )
    coding_section: Mapped["CodingSection | None"] = relationship(
        "CodingSection",
        back_populates="interview",
        uselist=False,
        cascade="all, delete-orphan",
    )


class TheorySection(Base):
    """Theory section record within an interview session.

    Stores theory-specific configuration, scoring, and section feedback.
    One interview may have at most one theory section.

    Attributes:
        id: Auto-increment primary key.
        interview_id: Foreign key to the parent Interview.
        selection_spec: JSON describing tracks, levels, and topic categories.
        question_count: Number of theory questions in this section.
        task_time_limit_seconds: Per-task time limit in seconds (None if disabled).
        status: Section status (``active``, ``completed``, or ``skipped``).
        section_score: Aggregated section score when evaluated.
        section_feedback: JSON string with section narrative feedback.
        locale: Language for AI feedback and follow-ups.
        interview: Back-reference to the parent Interview.
        tasks: Theory task rows linked to this section.
    """

    __tablename__ = "theory_sections"

    id: Mapped[int] = mapped_column(primary_key=True)
    interview_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("interviews.id", ondelete="CASCADE"),
        unique=True,
    )
    selection_spec: Mapped[str] = mapped_column(Text)
    question_count: Mapped[int] = mapped_column(default=5)
    task_time_limit_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String, default="active")
    section_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    locale: Mapped[str] = mapped_column(String, default="en", server_default="en")

    interview: Mapped["Interview"] = relationship(
        "Interview", back_populates="theory_section"
    )

    tasks: Mapped[list["Answer"]] = relationship(
        "Answer",
        back_populates="theory_section",
        order_by="Answer.order, Answer.round",
    )


class Answer(Base):
    """Theory task row persisted in the ``answers`` table.

    Each row represents one answer attempt: the initial answer (round=0)
    or a follow-up (round>0) when the AI digs deeper on a topic.

    Attributes:
        id: Auto-increment primary key.
        theory_section_id: Foreign key to the parent TheorySection.
        question_id: Question ID from YAML bank (e.g., "ds-001").
        order: Display order within the section (1-based).
        round: Follow-up round number (0 = initial, 1+ = follow-ups).
        question_text: Snapshot of the question text at time of asking.
        question_code: Snapshot of the optional code snippet.
        answer_text: User's answer text (None if skipped).
        score: AI-assigned score (1-5, or 0 on timeout), None if not yet evaluated.
        feedback: AI-generated feedback text.
        started_at: When this round became active for the user (None if timer off).
        created_at: Timestamp when this answer was recorded.
        theory_section: Back-reference to the parent TheorySection.
    """

    __tablename__ = "answers"

    id: Mapped[int] = mapped_column(primary_key=True)
    theory_section_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("theory_sections.id", ondelete="CASCADE"),
    )
    question_id: Mapped[str] = mapped_column(String)
    order: Mapped[int] = mapped_column()
    round: Mapped[int] = mapped_column(Integer, default=0)
    question_text: Mapped[str] = mapped_column(Text)
    question_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    theory_section: Mapped["TheorySection"] = relationship(
        "TheorySection", back_populates="tasks"
    )


class CodingSection(Base):
    """Coding section record within an interview session.

    Stores coding-specific configuration, scoring, and section feedback.
    One interview may have at most one coding section.

    Attributes:
        id: Auto-increment primary key.
        interview_id: Foreign key to the parent Interview.
        selection_spec: JSON describing tracks, levels, and topic categories.
        task_count: Number of coding tasks in this section.
        task_time_limit_seconds: Per-task time limit in seconds (None if disabled).
        status: Section status (``pending``, ``active``, ``completed``, or ``skipped``).
        section_score: Aggregated section score when evaluated.
        section_feedback: JSON string with section narrative feedback.
        locale: Language for AI feedback.
        interview: Back-reference to the parent Interview.
        tasks: Coding task rows linked to this section.
    """

    __tablename__ = "coding_sections"

    id: Mapped[int] = mapped_column(primary_key=True)
    interview_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("interviews.id", ondelete="CASCADE"),
        unique=True,
    )
    selection_spec: Mapped[str] = mapped_column(Text)
    task_count: Mapped[int] = mapped_column(default=1)
    task_time_limit_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String, default="active")
    section_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    locale: Mapped[str] = mapped_column(String, default="en", server_default="en")

    interview: Mapped["Interview"] = relationship(
        "Interview", back_populates="coding_section"
    )

    tasks: Mapped[list["CodingTask"]] = relationship(
        "CodingTask",
        back_populates="coding_section",
        order_by="CodingTask.order, CodingTask.round",
        cascade="all, delete-orphan",
    )


class CodingTask(Base):
    """Coding task row within a coding section.

    Attributes:
        id: Auto-increment primary key.
        coding_section_id: Foreign key to the parent CodingSection.
        task_id: Task ID from the coding bank.
        order: Display order within the section (1-based).
        round: Follow-up round number (0 = initial).
        prompt_text: Snapshot of the task prompt.
        task_spec: JSON with starter code and public test metadata.
        submitted_code: Final submitted source code (None if pending).
        submit_test_summary: JSON with hidden test results after submit.
        score: AI-assigned score (1-5, or 0 on timeout).
        feedback: AI-generated feedback text.
        started_at: When this round became active for the user.
        created_at: Timestamp when this task row was created.
        coding_section: Back-reference to the parent CodingSection.
        run_attempts: Code run attempts for this task.
    """

    __tablename__ = "coding_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    coding_section_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("coding_sections.id", ondelete="CASCADE"),
    )
    task_id: Mapped[str] = mapped_column(String)
    order: Mapped[int] = mapped_column()
    round: Mapped[int] = mapped_column(Integer, default=0)
    prompt_text: Mapped[str] = mapped_column(Text)
    task_spec: Mapped[str] = mapped_column(Text)
    submitted_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    submit_test_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    coding_section: Mapped["CodingSection"] = relationship(
        "CodingSection", back_populates="tasks"
    )

    run_attempts: Mapped[list["CodeRunAttempt"]] = relationship(
        "CodeRunAttempt",
        back_populates="coding_task",
        order_by="CodeRunAttempt.attempt_no",
        cascade="all, delete-orphan",
    )


class CodeRunAttempt(Base):
    """Immutable snapshot of one Run action on a coding task.

    Attributes:
        id: Auto-increment primary key.
        coding_task_id: Foreign key to the parent CodingTask.
        attempt_no: Sequential attempt number for the task.
        source_code: Editor contents at Run time.
        language: Programming language slug.
        status: Run outcome status.
        stdout: Captured standard output.
        stderr: Captured standard error.
        compile_output: Compiler output when applicable.
        tests_passed: Number of public tests passed.
        tests_total: Total public tests executed.
        test_results: JSON per-test result details.
        duration_ms: Judge0 execution duration in milliseconds.
        created_at: Timestamp when the attempt was recorded.
        coding_task: Back-reference to the parent CodingTask.
    """

    __tablename__ = "code_run_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    coding_task_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("coding_tasks.id", ondelete="CASCADE"),
    )
    attempt_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_code: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    stdout: Mapped[str | None] = mapped_column(Text, nullable=True)
    stderr: Mapped[str | None] = mapped_column(Text, nullable=True)
    compile_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    tests_passed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tests_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    test_results: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    coding_task: Mapped["CodingTask"] = relationship(
        "CodingTask", back_populates="run_attempts"
    )
