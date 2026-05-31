# Changelog

Versions use the release date: `YYYY.M.d` (newest first).

Work in progress is accumulated under `[Unreleased]`; on release, that section becomes the new dated version.

## [Unreleased]

### Added

### Changed

### Fixed

### Removed

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
