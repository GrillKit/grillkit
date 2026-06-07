# Changelog

Versions use the release date: `YYYY.M.d` (newest first).

Work in progress is accumulated under `[Unreleased]`; on release, that section becomes the new dated version.

## [Unreleased]

### Added

### Changed

- Interview WebSocket, NDJSON audio-answer, and wire JSON mapping live in `interview/api/` (`ws_session.py`, `audio_answer.py`, `ws_protocol.py`); use cases return `InterviewEvent` only
- Interview page and WebSocket/audio routes delegate to use-case services; speech runtime preload runs in `interview/api/routes` via `SpeechRuntimeCoordinator`
- Cross-feature active-session reads use `InterviewQuery.get_active_interview_or_raise` (removed `interview/services/access.py`)
- Persistence serialization (`selection_spec`, `overall_feedback`) moved to `interview/domain/serialization`; repository mappers no longer import `services/rules`
- Round timer start on interview page load uses aggregate `save_aggregate` instead of direct ORM answer mutations
- `load_active_interview_or_raise` via `InterviewQuery.get_active_interview_or_raise`
- Interview page template context assembled in `InterviewPageService.build_full_template_context` (speech and question-voice keys); `interview/api/routes` no longer imports speech/question_voice page services
- `InterviewRepository.list_recent` returns domain aggregates; dashboard maps them via `interview_to_read` only
- Answer-round AI evaluation consolidated in `InterviewEvaluatorService.evaluate_submission` (removed `AnswerAiEvaluationService`)
- Platform config uses shared speech/TTS catalogs (`app/shared/speech_models.py`, `app/shared/tts_voices.py`) and `WhisperReadinessService` instead of importing speech/question_voice feature rules

### Fixed

- Configuration speech model panel tracks the selected Whisper size and locale in the form (status, download, and save now refer to the same model)
- Whisper and Piper voices can be downloaded from Configuration before any LLM model is saved; adding an audio-capable catalog entry no longer requires Whisper to be installed first

### Removed

- Dead `platform/api/llm_page_context.py` and legacy ORM→read helpers in `interview/schemas/mappers.py`
- Unused `pydeps` runtime dependency
- `AnswerRepository`, `uow.answers`, and unused `speech/api/preload.py`
- `AnswerAiEvaluationService` (logic moved to `InterviewEvaluatorService.evaluate_submission`)
- Completed plan `docs/plans/domain-layer-migration.md`
- Unused `follow_ups` and `expected_points` fields from `Question` loader (`app/questions.py`); legacy YAML keys are ignored
- `speech/services/rules/` and `question_voice/services/rules/` (catalogs moved to `app/shared/`)

## 2026.5.31

### Added

- **Audio answers** — per-model “Accepts audio input” in the LLM catalog, WAV upload API, and Record / Send controls on the interview page (Whisper + multimodal model)
- **Question banks** — System Design; Kafka, RabbitMQ, Docker, Kubernetes, Observability, and Airflow tracks; expanded Python and Database categories (en/ru)
- **Alembic migrations** on startup and optional `DATABASE_URL` for the application database

### Changed

- Interview setup uses **track** terminology instead of language; the last follow-up on a question advances immediately while AI scoring finishes in the background

### Fixed

### Removed

## 2026.5.24

### Added

- Optional **per-round timer** on interview setup — expired rounds score 0 and the session moves on
- **Voice input** for answers — offline Whisper; download the model on `/config`
- **Question audio** (optional) — Piper TTS reads questions aloud; enable and download a voice on `/config`
- **LLM model catalog** in `data/llm_models.json` — API keys and model list live separately from `data/config.json`; pick the interview model on `/config`

### Changed

### Fixed

### Removed

## 2026.5.20

First release.

- AI interview sessions with WebSocket chat, scoring, and follow-ups
- Setup: language, level, topic, locale, question count
- Question banks: Python and Database/SQL (YAML)
- Dashboard, provider configuration, Docker Compose deployment
