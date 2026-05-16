# Copyright 2026 GrillKit Contributors
# SPDX-License-Identifier: Apache-2.0
"""SQLAlchemy models for GrillKit.

This module defines all database models, including interview sessions,
answers, and future entities.
"""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class InterviewSession(Base):
    """Interview session record.

    Stores the top-level metadata for an interview session.

    Attributes:
        id: Unique interview identifier (UUID v4).
        level: Interview difficulty level (junior, middle, senior).
        category: Question category (e.g., "python", "algorithms").
        question_count: Number of questions in this interview.
        question_ids: JSON list of question IDs in display order.
        status: Interview status ("active", "completed").
        score: Final total score (None if not graded yet).
        overall_feedback: JSON string with final evaluation feedback (None if not evaluated).
        started_at: Timestamp when interview began.
        completed_at: Timestamp when interview ended (None if active).
        answers: Relationship to Answer records, ordered by (order, round).
    """

    __tablename__ = "interview_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    level: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String)
    question_count: Mapped[int] = mapped_column(default=5)
    question_ids: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String, default="active")
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    overall_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    answers: Mapped[list["Answer"]] = relationship(
        "Answer",
        back_populates="interview_session",
        order_by="Answer.order, Answer.round",
        cascade="all, delete-orphan",
    )


class Answer(Base):
    """Individual answer record within an interview session.

    Each row represents one answer attempt: the initial answer (round=0)
    or a follow-up (round>0) when the AI digs deeper on a topic.

    Attributes:
        id: Auto-increment primary key.
        interview_session_id: Foreign key to the parent InterviewSession.
        question_id: Question ID from YAML bank (e.g., "ds-001").
        order: Display order within the session (1-based).
        round: Follow-up round number (0 = initial, 1+ = follow-ups).
        question_text: Snapshot of the question text at time of asking.
        question_code: Snapshot of the optional code snippet.
        answer_text: User's answer text (None if skipped).
        score: AI-assigned score (1-5), None if not yet evaluated.
        feedback: AI-generated feedback text.
        created_at: Timestamp when this answer was recorded.
        interview_session: Back-reference to the parent InterviewSession.
    """

    __tablename__ = "answers"

    id: Mapped[int] = mapped_column(primary_key=True)
    interview_session_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("interview_sessions.id", ondelete="CASCADE"),
    )
    question_id: Mapped[str] = mapped_column(String)
    order: Mapped[int] = mapped_column()
    round: Mapped[int] = mapped_column(Integer, default=0)
    question_text: Mapped[str] = mapped_column(Text)
    question_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    interview_session: Mapped["InterviewSession"] = relationship(
        "InterviewSession", back_populates="answers"
    )
