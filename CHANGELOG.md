# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Repository layer** (`app/repositories/`) — abstract `Repository[T]` interface and SQLAlchemy-backed `SqlAlchemyRepository[T]` base class.
- **`InterviewSessionRepository`** (`app/repositories/session.py`) — CRUD for sessions with eager-loading, `complete_session()`, `save_evaluation_feedback()`, and factory methods.
- **`AnswerRepository`** (`app/repositories/answer.py`) — CRUD for answers with lookup by session/question/round, `set_answer_text()`, `set_evaluation()`, `new_follow_up()` factory.
- **`UnitOfWork`** (`app/uow.py`) — atomic transaction coordinator with `commit()`, `rollback()`, and lazy-initialised repository accessors (`.sessions`, `.answers`).
- **WebSocket real-time interview chat** — new endpoint `WS /interview/{session_id}/ws` for bidirectional communication.
- **Unit tests for repositories** (`tests/test_repositories.py`) — 26 tests covering `SqlAlchemyRepository`, `InterviewSessionRepository`, and `AnswerRepository`.
- **Unit tests for UnitOfWork** (`tests/test_uow.py`) — 11 tests covering commit, rollback, flush, lazy init, and context manager behaviour.
- JSON protocol for WebSocket messages: `answer` (client → server), `saved`, `evaluating`, `feedback`, `session_completed`, `error` (server → client).
- `InterviewSessionService._find_current_answer()`, `_find_next_unanswered()`, and `_evaluate_and_save()` helper methods.
- `WsSend` callback type alias — WebSocket endpoint passes `send_json` callback to service layer.
- `ws_send` parameter on `process_answer_submission()` and `process_session_completion()` — send intermediate events (saved, evaluating, feedback, session_completed).
- Real-time feedback display in interview template: answer bubble → evaluating spinner → score/feedback/follow-up.
- CSS spinner animation (`.spinner`, `.evaluating-indicator`) for "AI is evaluating..." state.
- `{% block scripts %}` in `base.html` for per-template JavaScript blocks.
- AI-powered answer evaluation: each answer is scored 1-5 with detailed feedback.
- AI-powered follow-up questions: if answer is insufficient, AI generates a probing follow-up (up to 2 per question).
- AI-powered session evaluation: final overall feedback, strengths, topics to review, and score breakdown.
- `InterviewEvaluatorService` (`app/services/interview_evaluator.py`) with Pydantic models for structured AI output.
- `AnswerEvaluation`, `FollowUpEvaluation`, `SessionEvaluation` Pydantic models with JSON schema embedded in prompts.
- `overall_feedback` field on `InterviewSession` model (JSON string with final evaluation).
- `save_evaluation()` and `save_session_evaluation()` methods on `InterviewSessionService`.
- `process_answer_submission()` and `process_session_completion()` orchestration methods.
- Final evaluation section in interview template (overall feedback, strengths, topics, score table).
- CSS styles for feedback sections and score breakdown table.
- Navigation bar in `base.html` with links to Dashboard, New Interview, Configuration.
- `POST /interview/{session_id}/complete` endpoint to end an interview session.
- Dashboard page with empty state and call-to-action buttons.

### Changed
- **Service layer refactored** — `InterviewSessionService` no longer depends on raw SQLAlchemy sessions. All DB access is now through `InterviewSessionRepository`, `AnswerRepository`, and `UnitOfWork`.
- **Removed** module-level helpers `_get_answer_record()` and `_add_follow_up_record()` — replaced by repository methods.
- **Removed** dead code: `submit_answer()`, `save_evaluation()`, `save_session_evaluation()` — these public methods were unused (logic was duplicated inline).
- **Removed** unused `uow_scope()` context manager from `app/uow.py`.
- **Data access pattern** — all write operations now use `with UnitOfWork(auto_commit=True) as uow:` for atomicity; read-only queries use transient `UnitOfWork()`.
- **Detached session fix** — `_evaluate_and_save()` now re-loads session and answer objects inside the UoW to prevent `DetachedInstanceError`.
- `templates/interview.html` — initial page loads via HTTP (full history), then all interaction via WebSocket.
- `process_answer_submission()` and `process_session_completion()` accept optional `ws_send` callback.
- `ARCHITECTURE.md` — added WebSocket data flow, updated project map and limitations.
- `InterviewSessionService._evaluate_and_save()` — refactored to eliminate code duplication between initial and follow-up evaluation branches.
- `InterviewSessionService._find_next_unanswered()` — optimized from O(n²) to O(n) using set lookup.
- **Per-question score/feedback no longer displayed during active interview** — AI evaluation is saved to DB silently; all scores and feedback are shown only after session completion in the final evaluation section.
- `InterviewSessionService._build_feedback_ws_event()` — removed `score`, `feedback`, `strengths`, `weaknesses` from WebSocket `feedback` event.
- `templates/interview.html` — removed per-question score/feedback bubbles from chat rendering for active sessions; replaced `showFeedback()` JS function with `showNextAfterFeedback()` that only advances to the next question.

### Fixed
- Follow-up evaluation now passes the original question text (not the follow-up text itself) to AI for proper context.
- AI provider connection now properly closed after evaluation to prevent resource leaks.
- `POST /interview/{session_id}/answer` now returns 400 with a clear message if the session is already completed.
- `InterviewSessionService._evaluate_and_save()` — `provider.close()` no longer raises `NameError` if `create_provider_from_config()` fails.
- `InterviewSessionService.process_session_completion()` — same `NameError` fix for `provider.close()` in `finally` block.

[unreleased]: https://github.com/yourusername/grillkit/compare/HEAD...HEAD