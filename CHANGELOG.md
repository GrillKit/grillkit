# Changelog

Versions use the release date: `YYYY.M.d` (newest first).

Work in progress is accumulated under `[Unreleased]`; on release, that section becomes the new dated version.

## [Unreleased]

### Added

### Changed

### Fixed

### Removed

## 2026.6.16

### Added

- **Known questions** — mark theory or coding bank items as known during an interview (**I know this**) or on review pages; optionally exclude them when starting a new session; manage the list from **Known Questions** in the navigation bar

### Changed

- **Add model to catalog** — the catalog model id is generated automatically from the display name; removed the **Model id** field on `/config`
- **UI** — refreshed dark theme with clearer hierarchy, IDE-style coding editor, terminal-style run output, and updated status badges on the dashboard

### Fixed

- **Theory then coding sessions** — fixed errors when advancing from theory to coding in a combined session
- **Coding follow-ups** — explanation rounds now submit your typed explanation instead of the code in the editor
- **Coding timers** — expired rounds score 0 and the session advances automatically
- **Setup review** — known-questions option shows the correct hint for the checkbox
- **Early session end** — partial theory/coding scores are kept when you end a session before finishing every task
- **Theory answers** — more reliable submit flow for text and audio answers during AI evaluation
- **Dashboard** — faster interview history on the home page

### Removed

## 2026.6.12

### Added

- **Coding interviews** — practice live coding in the browser: editor, Run on public tests, Submit for evaluation, and a review page after the session; use `docker compose --profile coding` for code execution
- **Coding question bank** — 33 Python language-focused tasks (junior: basics, strings, functions, control flow, exceptions, OOP, collections; middle: refactor, bug hunt, complete code, implement)

### Changed

- **New interview setup** — choose session mode (theory only, coding only, or both in sequence) and configure theory and coding topics separately on one screen

### Fixed

- **First-time configuration** — saving provider settings and downloading Whisper or Piper models works on a fresh install, including in Docker

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
