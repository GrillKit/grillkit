# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **WebSocket real-time interview chat** — new endpoint `WS /interview/{session_id}/ws` for bidirectional communication.
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
- `templates/interview.html` — initial page loads via HTTP (full history), then all interaction via WebSocket.
- `process_answer_submission()` and `process_session_completion()` accept optional `ws_send` callback.
- `ARCHITECTURE.md` — added WebSocket data flow, updated project map and limitations.
- `InterviewSessionService._evaluate_and_save()` — refactored to eliminate code duplication between initial and follow-up evaluation branches.
- `InterviewSessionService._find_next_unanswered()` — optimized from O(n²) to O(n) using set lookup.

### Fixed
- Follow-up evaluation now passes the original question text (not the follow-up text itself) to AI for proper context.
- AI provider connection now properly closed after evaluation to prevent resource leaks.
- `POST /interview/{session_id}/answer` now returns 400 with a clear message if the session is already completed.
- `InterviewSessionService._evaluate_and_save()` — `provider.close()` no longer raises `NameError` if `create_provider_from_config()` fails.
- `InterviewSessionService.process_session_completion()` — same `NameError` fix for `provider.close()` in `finally` block.

[unreleased]: https://github.com/yourusername/grillkit/compare/HEAD...HEAD