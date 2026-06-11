# GrillKit

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-yellow.svg)](https://opensource.org/licenses/Apache-2.0)
[![Version](https://img.shields.io/badge/version-2026.5.31-blue.svg)](CHANGELOG.md)

Open-source AI technical interview trainer. Practice from curated YAML question banks, get structured scoring and follow-ups, and optionally use voice — with your own LLM (cloud or local).

[Why GrillKit](#why-grillkit-not-just-chatgpt) · [Quick start](#quick-start) · [Changelog](CHANGELOG.md) · [Architecture](ARCHITECTURE.md)

## Why GrillKit (not just ChatGPT)

A general chat assistant is flexible, but it does not run an **interview** for you.

| What you need | ChatGPT-style chat | GrillKit |
|---------------|-------------------|----------|
| Curated technical questions | You prompt each time | Built-in **tracks** (Python, Kafka, System Design, …), **levels**, and **topics** |
| Interview flow | Free-form thread | Fixed session: N questions, up to **2 AI follow-ups** per question, **1–5 scoring**, session summary |
| Practice history | Scattered chats | **Dashboard** with past sessions stored locally |
| Time pressure | None | Optional **per-round timer** (expired round → 0, move on) |
| Voice practice | Depends on product | Offline **Whisper** dictation; optional **Piper** question audio; **audio answers** when your model supports it |
| Where data lives | Vendor cloud | **Self-hosted**: SQLite + `data/` on your machine; use **Ollama**, vLLM, or any OpenAI-compatible API |

**Structured practice** — You pick tracks, difficulty, and topics; GrillKit builds a question plan and keeps score across the whole session, not a single ad-hoc prompt.

**Privacy and control** — Run via Docker on your laptop or server. API keys and interview history stay under `./data` (gitignored). No account or subscription required beyond your LLM provider (if you use a cloud model).

## Screenshots & demo

**Demo video** — full flow from setup to scored feedback

<p align="center">
  <img src="./assets/demo_cut.gif" alt="Demo video" width="900" />
</p>

**Dashboard** — recent sessions and quick start

<p align="center">
  <img src="./assets/dashboard.png" alt="GrillKit dashboard" width="900" />
</p>

**Interview setup** — question-bank tracks, levels, topics, and session options

<p align="center">
  <img src="./assets/interview-setup.png" alt="Interview setup" width="900" />
</p>

**Interview session** — real-time Q&A with AI scoring and final evaluation

<p align="center">
  <img src="./assets/interview-session.png" alt="Completed interview with evaluation" width="900" />
</p>

## Features

- **Interviews** — multi-track setup, several topics per session, WebSocket Q&A, AI scoring 1–5, up to 2 follow-ups per question
- **Question banks** — Python, Database/SQL, System Design, Kafka, RabbitMQ, Docker, Kubernetes, Observability, Airflow, and more under `data/questions/{track}/` (junior / middle / senior where applicable)
- **Timer** — optional per-round time limit; expired rounds score 0 and the session moves on
- **Voice** — offline Whisper dictation for typed answers; optional Piper TTS to read questions aloud
- **Audio answers** — when the configured model supports audio input and Whisper is ready, record and send a WAV answer from the interview page
- **Setup** — model catalog on `/config`, interview locale (AI feedback language), Whisper/Piper downloads from the UI
- **Dashboard** — recent interview history on the home page
- **Deployment** — Docker Compose on port 8000 with `./data` volume for config, DB, and models

## Quick start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/)
- API key for a cloud provider, **or** a local OpenAI-compatible server (Ollama, vLLM, …)

### Run with Docker

```bash
git clone https://github.com/yourusername/grillkit.git
cd grillkit
docker compose up --build
```

Open [http://localhost:8000](http://localhost:8000).

Optional **question voice** (Piper TTS, same `app` container):

1. Run `docker compose up` (or `uv run uvicorn app.main:app` for development).
2. Open `/config`, enable **Read questions aloud**, save.
3. On the Configuration page, use **Download question voice** when prompted (~60 MB per locale voice from Hugging Face).
4. Start an interview — questions can play aloud; WAV cache lives under `data/tts-cache/v2/{locale}/`.

`./data` on the host holds SQLite, `config.json`, `llm_models.json`, Whisper/Piper models, and TTS cache. Question banks, templates, and static files ship in the image.

If bind-mounted `data/` is not writable (Linux UID mismatch):

```bash
PUID=$(id -u) PGID=$(id -g) docker compose up --build
```

**Coding sessions** (Monaco + code execution) require [Judge0 CE](https://github.com/judge0/judge0). Start the optional `coding` profile:

```bash
docker compose --profile coding up --build
```

Judge0 listens on port `2358` inside the Compose network (`JUDGE0_URL=http://judge0-server:2358` for the `app` service). For local development without Docker, run Judge0 separately and point `JUDGE0_URL` at `http://localhost:2358`.

On some Linux hosts Judge0 needs **cgroup v1** (`systemd.unified_cgroup_hierarchy=0` in GRUB). Set `CODING_ENABLED=false` to hide coding modes when Judge0 is unavailable.

### First-time flow

1. **Configuration** (`/config`) — add one or more OpenAI-compatible models to the catalog, select an interview model, set interview locale; test connection, then save.
2. **New interview** (`/setup`) — pick a **session mode** (theory only, coding only, or combined). Configure theory and/or coding tracks, topics, task counts, and per-task timers. Coding modes require Judge0 (see **Coding sessions** above).
3. **Interview** (`/interview/{id}`) — theory answers over `WS /theory/ws`; coding uses Monaco + Run (`POST /coding/run`) and Submit (`WS /coding/ws`). End interview from the sidebar at any time.

Without saved provider config, `/setup` redirects to `/config`.

### Local development

For contributors: see [CONTRIBUTING.md](CONTRIBUTING.md). Quick run:

```bash
uv sync --extra dev
uv run uvicorn app.main:app --reload
```

Same first-time flow at [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Configuration (essentials)

Any **OpenAI-compatible** HTTP API works:

| Provider | Example base URL |
|----------|------------------|
| OpenAI | `https://api.openai.com/v1` |
| Ollama | `http://localhost:11434/v1` |
| vLLM / others | your endpoint + `/v1` |

On `/config`:

- **Add model to catalog** — base URL, model name, optional API key; enable **Accepts audio input** only if the model supports multimodal audio (and download Whisper for transcription).
- **Interview model** — pick from the catalog, **Test Connection**, save.
- **Locale** — language for AI feedback and speech (stored in `data/config.json`, gitignored).
- **Whisper** — choose size (`small`, `medium`, `large`), download from the UI for dictation and audio answers.
- **Read questions aloud** — enable Piper, download a voice (~60 MB).

Do not commit `data/config.json`, `data/llm_models.json`, or API keys.

Optional environment variables (full list in [ARCHITECTURE.md](ARCHITECTURE.md#persistence--configuration)):

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | SQLAlchemy URL (default: SQLite under `data/db/`) |
| `HF_TOKEN` | Hugging Face token for faster Whisper/Piper downloads |
| `WHISPER_DEVICE` | `cpu` or `cuda` |
| `WHISPER_COMPUTE_TYPE` | `int8` or `float16` |
| `CODING_ENABLED` | Enable coding session modes (default `true`; requires healthy Judge0) |
| `JUDGE0_URL` | Judge0 API base URL (default `http://localhost:2358`) |
| `JUDGE0_AUTH_TOKEN` | Optional Judge0 `X-Auth-Token` header |
| `CODING_MAX_RUNS_PER_TASK` | Max Run attempts per coding task (default `20`) |

## Roadmap

**Planned**

- Session-wide time limit (total interview duration)
- More question banks and categories
- Custom question banks, PWA / standalone frontend

## For developers

| Document | Contents |
|----------|----------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Layers, HTTP/WebSocket routes, data flows, persistence, question banks |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Dev setup, tests, ruff/mypy/pytest, contribution workflow |
| [CHANGELOG.md](CHANGELOG.md) | Release history |

## Security

Report vulnerabilities as described in [SECURITY.md](SECURITY.md). Do not open public issues for security problems.

## License

[Apache License 2.0](LICENSE) (see also [NOTICE](NOTICE))
