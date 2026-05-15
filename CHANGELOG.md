# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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