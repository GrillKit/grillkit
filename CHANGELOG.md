# Changelog

Versions use the release date: `YYYY.M.d` (newest first).

Work in progress is accumulated under `[Unreleased]`; on release, that section becomes the new dated version.

## [Unreleased]

### Added

- Offline **Whisper** speech recognition via faster-whisper with configurable model size (`small`, `medium`, `large`) and trade-off hints on `/config`
- Server-side model download (`/speech/model/status`, `/speech/model/download`, `/speech/model/options`) with in-process hot-reload after install
- Interview dictation WebSocket (`/interview/{id}/dictation`): buffer PCM on the server, transcribe on stop with `language` from interview locale
- Voice input button on the interview page (mic records answer audio; transcript appears after stop)

### Changed

- Reorganize `app/` into feature-first packages: `interview/`, `speech/`, `platform/`, and `shared/` (domain, infrastructure, repositories)
- Declare `huggingface-hub` as a direct dependency for Whisper model downloads
- Move interview language (`locale`) to provider configuration: set on `/config`, read-only on setup, snapshot when creating a session
- Show the user's answer in chat as soon as they submit; AI evaluation continues in the background
- AI evaluator prompts: score technical substance, not grammar or speech-to-text artifacts in dictated answers

### Removed

- Vosk per-locale speech models (`data/vosk-models/`, `vosk` dependency)

## 2026.5.20

First release.

- AI interview sessions with WebSocket chat, scoring, and follow-ups
- Setup: language, level, topic, locale, question count
- Question banks: Python and Database/SQL (YAML)
- Dashboard, provider configuration, Docker Compose deployment
