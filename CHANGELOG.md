# Changelog

Versions use the release date: `YYYY.M.d` (newest first).

Work in progress is accumulated under `[Unreleased]`; on release, that section becomes the new dated version.

## [Unreleased]

### Added

- `DATABASE_URL` environment variable for SQLAlchemy connection string (default: SQLite file under `data/db/grillkit.db`)
- Alembic migrations for SQLite schema and `selection_spec` data upgrade (`language` → `track`)
- Question banks (bilingual en/ru, ~141 new questions): **Python** — junior/middle/senior categories for FastAPI, Django, Django REST Framework, pytest, and asyncio; **Database** — SQLite and Redis basics (junior), locking/concurrency, migrations, and Redis advanced (middle), ClickHouse analytics (senior)
- **System Design** question bank (language-agnostic): middle fundamentals and senior distributed systems / advanced architecture topics
- **Kafka** question bank (18 questions, bilingual en/ru): platform topics in `kafka/` (junior fundamentals, middle messaging and storage, senior cluster architecture and stream processing); Python client topics in `python/{junior,middle,senior}/kafka.yaml` (libraries through production EOS, schema registry, and multiprocessing)
- **RabbitMQ** question bank (17 questions, bilingual en/ru): platform topics in `rabbitmq/` and Python client topics in `python/{junior,middle,senior}/rabbitmq.yaml`
- **Docker** question bank (7 questions, bilingual en/ru): junior fundamentals, middle operations, senior security in `docker/`
- **Kubernetes** question bank (10 questions, bilingual en/ru): junior fundamentals, middle networking/scheduling, senior production in `kubernetes/`
- **Observability** question bank (18 questions, bilingual en/ru): Prometheus, Grafana, and Loki topics in `observability/` across junior/middle/senior levels
- **Airflow** question bank (15 questions, bilingual en/ru): fundamentals, executors, scheduling, operations, TaskFlow, and production topics in `airflow/`

### Changed

- Interview feature: three-layer flow (`api` → `services` → `repositories`) with Pydantic read models in `app/interview/schemas/`; API no longer uses SQLAlchemy ORM types directly; WebSocket server messages typed in `app/interview/schemas/ws.py`
- Speech and question-voice features: Pydantic status/page schemas; page context built in services (`SpeechModelPageService`, `QuestionVoicePageService`)
- Platform feature: `AppConfigRead`, `ConfigPageContext`, LLM preset read models; `ConfigPageService` and `ConfigFormService`; configuration API delegates to services
- Removed feature `domain/` packages: business rules and metadata live under `services/`; shared `exceptions` and `locales` at `app/shared/` top level
- `selection_spec` JSON: `language` → **track**, dropped `version` field; domain types and setup UI/API use **track** terminology (`TrackSelection`, `list_tracks`, `/setup/options?track=…`)
- Question bank YAML metadata: top-level `language` field renamed to **track** (loader uses directory path; field is documentation only)
- README and ARCHITECTURE updated for **track** terminology, System Design bank, and Alembic migrations (replaces manual DB reset for schema changes)
- Moved language-agnostic system design questions out of the Python bank into `data/questions/system-design/`; Python-specific topics (consensus in Python, data pipelines, ADRs, chaos engineering) remain under `python/senior`
- Renumbered system design question IDs to be sequential within each YAML file (`sd-*`, `dsys-*`, `aad-*`, `psd-*`)

### Fixed

- Docker image includes `alembic.ini` and migration scripts so `run_migrations()` runs on container startup
- Removed erroneous `uliweb-alembic` dependency that shadowed the real `alembic` package and broke startup

### Removed

- LLM catalog legacy fields `base_url_local` and `base_url_docker`; catalog entries use `base_url` only

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
