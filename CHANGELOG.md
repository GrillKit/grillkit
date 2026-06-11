# Changelog

Versions use the release date: `YYYY.M.d` (newest first).

Work in progress is accumulated under `[Unreleased]`; on release, that section becomes the new dated version.

## [Unreleased]

### Added

- **Session results hub** — completed interviews redirect to `/interview/{id}/results` with overall evaluation and per-section summary cards linking to dedicated review pages
- **Theory review page** — `/interview/{id}/theory` shows section feedback and full Q&A chat history with per-round scores after session completion
- **Coding review page** — `/interview/{id}/coding` shows section feedback and an accordion of coding tasks with final submit, test summary, and per-round feedback on one page
- **Coding section evaluator** — `CodingEvaluatorService.evaluate_section()` prefetches `coding_sections.section_feedback` when the coding phase completes and before session completion
- **Coding interview UI** — separate coding panel with Monaco editor (CDN), Run (`POST /coding/run`), Submit (`WS /coding/ws`), run output with test progress, `sessionStorage` drafts, and phase switch between theory and coding by `session_mode`
- **CodingEvaluatorService** — AI scoring for coding submit with run history and hidden test context in prompts; `follow_up_mode: code | explanation`; hidden test failures cap score at 3
- **Coding Run API** — `POST /interview/{id}/coding/run` executes public tests via Judge0 and persists `CodeRunAttempt`; `GET /interview/{id}/coding/state` returns current task, progress, and run history; `WS /interview/{id}/coding/ws` accepts submit and streams `feedback`
- **Judge0 coding runner** — `CodingRunnerService` executes public tests and compile-only checks via `Judge0Client`; Python harness wraps candidate code for entrypoint tasks; setup blocks coding when Judge0 is unhealthy (`CODING_ENABLED` + health probe)
- **Judge0 Docker profile** — `docker compose --profile coding up` starts Judge0 CE (server, worker, Postgres, Redis); `deploy/judge0.conf` and env vars `JUDGE0_URL`, `JUDGE0_AUTH_TOKEN`
- **Coding setup and planning** — all four `session_mode` options on setup when coding is available; `GET /setup/coding-options` and `GET /setup/coding-available`; `app/coding/services/planning.py` picks tasks from `data/coding/`; `SessionCreationService` creates coding sections via `CodingSectionCreationService`
- **Dashboard session mode badge** — history rows show Theory, Coding, or Theory+Coding from `session_mode`
- **`app/theory/` module scaffold** — domain (`TheorySection`, `TheoryTask`), repositories, read schemas, and `theory_sections` table with backfill from existing interviews
- **Theory section tasks** — `answers.theory_section_id` links tasks to sections; theory repository loads full aggregate; interview creation dual-writes theory section rows
- **Theory submission services** — answer processing, navigation, timer, and evaluation persistence moved to `app/theory/services/`; WebSocket and audio API use `TheorySubmissionService`
- **Theory API routes** — canonical `POST /interview/{id}/theory/audio-answer` and `WS /interview/{id}/theory/ws`; legacy `/audio-answer` and `/ws` delegate with deprecation log; interview page uses new paths
- **Theory evaluator** — `app/theory/services/evaluator/` with `TheoryEvaluatorService`; per-task evaluation used by theory submission; `InterviewEvaluatorService` remains a compat alias
- **Session creation split** — `SessionCreationService` persists an interview shell plus `TheorySectionCreationService`; `Interview.start_shell` and theory-aware `interview_from_orm` reads
- **Selection spec v2** — `SessionSelection` with `session_mode`, theory/coding branches; setup form session-mode picker (coding modes shown as coming soon); Alembic backfill for legacy rows
- **Session page composition** — `SessionPageService` merges shell + `TheoryPageContext`; phase order from `session_mode`
- **Session evaluation pipeline** — `SessionEvaluationAggregator`, `SessionEvaluatorService`, and `InterviewSection` protocol with theory prefetch via `on_phase_complete`

### Changed

- **Section orchestration consolidation** — typed `SectionService` protocol with `is_user_facing` / `activate_if_pending`, shared section evaluation/review helpers, session evaluation models moved to `app/shared/evaluation_models.py`, multi-section score fallback sums both sections, unified results hub card builder via section registry, `score_breakdown` attached only at session completion via `attach_session_score_breakdown`
- **Session orchestration refactor** — unified `SESSION_MODE_LABELS`, section service registry instead of unused `InterviewSection` protocol, single `InterviewUnitOfWork` for cross-section phase reads, shared section-feedback prefetch and task timer helpers, score resolution moved out of mappers
- **Completed session navigation** — dashboard history links to `/interview/{id}/results`; active interview pages no longer embed final evaluation in the sidebar
- **Session completion scoring** — `SessionCompletionService` merges theory and coding section summaries; `score_breakdown` exposes separate `theory` and `coding` totals; display score sums both sections
- **Theory question planning** — excludes legacy `type: coding` rows still present in theory YAML banks
- **Documentation** — `ARCHITECTURE.md` coding data flows and scoring; `README.md` setup/coding env vars; `CONTRIBUTING.md` coding task YAML format
- **Coding naming** — domain/ORM fields use `task_count`, `task_id`, and `prompt_text` instead of legacy `question_*` names; `CodingSectionCreationService` requires shared `InterviewUnitOfWork` like theory
- **Shared paths and questions** — `app/paths.py` and `app/questions.py` moved to `app/shared/paths.py` and `app/shared/questions.py`
- **Theory question planning** — moved to `app/theory/services/planning.py`; excludes YAML `type: coding` rows
- **Session read models** — `AnswerRead` is an alias of `TheoryTaskRead`; interview domain no longer defines an `Answer` entity
- **Interview aggregate** — `Interview` is a session shell only; answers and theory config are composed at read time from `theory_sections`
- **Interview completion** — `SessionCompletionService` loads read models and scores from merged section breakdown
- **Interview creation** — setup uses `SessionCreationService.create_session` with shell + theory section persistence
- **Setup form** — posts v2 `selection_json`; theory question count and timer stored on the theory branch

### Fixed

- **Coding session UI** — dedicated `coding_interview.html` layout (assignment panel + editor); evaluating spinner no longer visible on load (`[hidden]` vs `display:flex` clash)
- **Coding task bank** — tasks use `coding.assignment` (technical brief) instead of theory-style `question.text` prompts
- **Coding-only session pages** — dashboard and interview page no longer 500 when theory sources are empty; titles and selection summary use coding branch data
- **Coding phase activation** — `theory_then_coding` sessions promote coding sections from `pending` to `active` when theory finishes (`SessionPhaseOrchestrator`, `CodingPageService.activate_timer`)
- **Theory-to-coding handoff** — completing the theory section auto-reloads into the coding page via shared `session_phases.js`; theory-complete state shows a **Continue to Coding** button as fallback
- Configuration speech model panel tracks the selected Whisper size and locale in the form (status, download, and save now refer to the same model)
- Per-question timer stops when the interview is ended or completed (including during final evaluation)
- Configuration question voice panel tracks the selected interview language in the form (status and download now refer to the matching Piper voice)
- Whisper and Piper voices can be downloaded from Configuration before any LLM model is saved; adding an audio-capable catalog entry no longer requires Whisper to be installed first

### Removed

- **Legacy interview columns** — `question_count`, `question_ids`, `question_time_limit_seconds`, and `score` dropped from `interviews`; `answers.interview_id` removed (Alembic `20260608_0007`)
- **Deprecated interview API paths** — `POST /interview/{id}/audio-answer` and `WS /interview/{id}/ws`; use `/theory/audio-answer` and `/theory/ws`
- **Interview compat re-exports** — `AnswerProcessingService`, `InterviewPageService`, `InterviewCreationService`, `InterviewCompletionService`, and `app/interview/services/evaluator/`

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
