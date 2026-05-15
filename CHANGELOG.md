# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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

### Fixed
- Follow-up evaluation now passes the original question text (not the follow-up text itself) to AI for proper context ([#Bug]).
- AI provider connection now properly closed after evaluation to prevent resource leaks.
- `POST /interview/{session_id}/answer` now returns 400 with a clear message if the session is already completed.
- Template layout: all pages now use `.app-container` + `.main-content` wrapper.
- `config_form.html` is now a partial (no `{% extends %}`) to avoid double layout when included.
- `config_form.html` uses proper CSS classes (`form-group`, `form-control`, `btn`, `card`).
- `config_success.html` uses `card`/`alert`/`btn` classes instead of non-existent `.success`/`.button`.
- `config_test_result.html` uses existing `.test-result.success`/`.test-result.error` classes.
- Interview chat now only shows answered questions + current unanswered question (not all future questions).
- Database refactoring: models moved to `app/models.py`, DB directory changed to `data/db/`.
- `InterviewSession` model (replaces old `Interview`) with `question_ids` and `question_count`.
- `Answer` model with support for follow-up rounds (`order`, `round` fields).
- `InterviewSessionService` for session CRUD, answer submission, and follow-up creation.
- Real `POST /setup` endpoint — creates a session from YAML question bank and redirects to interview page.
- Dynamic category loading in setup form from YAML question bank.
- Interview page (`GET /interview/{session_id}`) with chat-like answer history and form for current question.
- Interview chat CSS styles (question/answer/feedback bubbles, code blocks).
- `get_available_categories()` helper to list all categories across levels.

### Changed
- `app/services/config.py`: `DATA_DIR` replaced with local `CONFIG_DIR` path.
- `app/main.py`: registered new interview router.
- `app/api/__init__.py`: exported new interview router.
- Tests updated for new model names and removed `DATA_DIR` dependency.

### Fixed
- Test suite passes cleanly (75 tests).

[unreleased]: https://github.com/yourusername/grillkit/compare/HEAD...HEAD