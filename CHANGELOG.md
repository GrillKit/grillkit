# Changelog

Versions use the release date: `YYYY.M.d` (newest first).

Work in progress is accumulated under `[Unreleased]`; on release, that section becomes the new dated version.

## [Unreleased]

### Added

- Alembic migrations for SQLite schema and `selection_spec` data upgrade (`language` → `track`)
- Question banks (bilingual en/ru, ~141 new questions): **Python** — junior/middle/senior categories for FastAPI, Django, Django REST Framework, pytest, and asyncio; **Database** — SQLite and Redis basics (junior), locking/concurrency, migrations, and Redis advanced (middle), ClickHouse analytics (senior)
- **System Design** question bank (language-agnostic): middle fundamentals and senior distributed systems / advanced architecture topics

### Changed

- `selection_spec` JSON: `language` → **track**, dropped `version` field; domain types and setup UI/API use **track** terminology (`TrackSelection`, `list_tracks`, `/setup/options?track=…`)
- Question bank YAML metadata: top-level `language` field renamed to **track** (loader uses directory path; field is documentation only)
- README and ARCHITECTURE updated for **track** terminology, System Design bank, and Alembic migrations (replaces manual DB reset for schema changes)
- Moved language-agnostic system design questions out of the Python bank into `data/questions/system-design/`; Python-specific topics (consensus in Python, data pipelines, ADRs, chaos engineering) remain under `python/senior`
- Renumbered system design question IDs to be sequential within each YAML file (`sd-*`, `dsys-*`, `aad-*`, `psd-*`)

### Fixed

- Docker image includes `alembic.ini` and migration scripts so `init_db()` runs on container startup
- Removed erroneous `uliweb-alembic` dependency that shadowed the real `alembic` package and broke startup

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
