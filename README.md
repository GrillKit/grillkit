# GrillKit

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-yellow.svg)](https://opensource.org/licenses/Apache-2.0)
[![Version](https://img.shields.io/badge/version-2026.5.20-blue.svg)](CHANGELOG.md)

Open-source AI technical interview trainer. Configure an OpenAI-compatible model, pick a topic from YAML question banks, and practice in a real-time WebSocket interview with scoring and feedback.

Release notes: [CHANGELOG.md](CHANGELOG.md) · Architecture: [ARCHITECTURE.md](ARCHITECTURE.md)

## Features

- **Interviews** — create a session (language, level, topic, locale, question count), answer in the browser, end when done
- **Real-time chat** — `WS /interview/{id}/ws`: save answer → AI evaluation → score/feedback → optional follow-up or next question
- **Scoring** — each round scored 1–5 by the AI; totals and breakdown shown after you end the interview
- **Follow-ups** — AI-generated probing questions when an answer is insufficient (up to 2 per question)
- **Question banks** — Python and Database/SQL, junior / middle / senior (`data/questions/`)
- **Locales** — AI feedback language: English, Russian, French, Spanish, German (question text stays in the bank language)
- **Dashboard** — recent interview history on the home page
- **Provider setup** — configure and test an OpenAI-compatible API; settings in `data/config.json`
- **Persistence** — SQLite (`data/db/grillkit.db`) for interviews and answers
- **Docker Compose** — recommended way to run locally (port 8000, `./data` volume)

## Roadmap

**In progress**

- Voice input and output in the interview UI
- Interview timer (session time limit)
- Optional local model for the interview (e.g. Ollama alongside cloud provider)
- Response time per question

**Planned**

- More question banks (Go, JavaScript, Java, C++, …)
- Code editor in the interview UI
- Custom question banks, PWA / standalone frontend

## Quick start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/)
- API key for a cloud provider, **or** a local server (e.g. [Ollama](https://ollama.com/)) with an OpenAI-compatible endpoint

### Run with Docker

```bash
git clone https://github.com/yourusername/grillkit.git
cd grillkit
docker compose up --build
```

Open [http://localhost:8000](http://localhost:8000).

`./data` on the host holds SQLite and `config.json`. Question banks, templates, and static files are in the image.

If bind-mounted `data/` is not writable (Linux UID mismatch):

```bash
PUID=$(id -u) PGID=$(id -g) docker compose up --build
```

### First-time flow

1. **Configuration** (`/config`) — provider type, base URL, model, optional API key; test connection, then save.
2. **New interview** (`/setup`) — language → level → topic, locale, number of questions.
3. **Interview** (`/interview/{id}`) — page loads history; answers and completion go over WebSocket.

Without saved provider config, `/setup` redirects to `/config`.

### Local development

```bash
uv sync --extra dev
uv run uvicorn app.main:app --reload
```

Same first-time flow at [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Configuration

Any **OpenAI-compatible** HTTP API works (single adapter in code):

| Provider | Example base URL |
|----------|------------------|
| OpenAI | `https://api.openai.com/v1` |
| Ollama | `http://localhost:11434/v1` |
| vLLM / others | your endpoint + `/v1` |

Secrets and model name are stored in `data/config.json` (gitignored). Do not commit API keys.

## Data layout

```
data/
├── config.json       # AI provider (gitignored)
├── db/grillkit.db    # SQLite (gitignored, created on startup)
└── questions/        # YAML banks: {language}/{level}/{category}.yaml
```

There are no database migrations yet. After a schema change, remove `data/db/grillkit.db` and restart the app to recreate tables.

## Project layout

```
app/
├── main.py           # FastAPI app, routers, static files
├── api/              # HTTP + WebSocket routes
├── services/         # Use cases (create, answer, complete, evaluate, config)
├── domain/           # Progress, scoring rules, exceptions, locales
├── repositories/     # SQLAlchemy data access
├── uow.py            # Unit of Work
├── ai/               # OpenAI-compatible provider
├── models.py         # Interview, Answer
└── questions.py      # YAML loader
templates/            # Jinja2 UI
static/               # CSS
tests/
ARCHITECTURE.md       # Layers, routes, data flows
```

## Development

```bash
uv run pytest
uv run ruff check --fix .
uv run ruff format .
uv run mypy .
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

## Security

Report vulnerabilities as described in [SECURITY.md](SECURITY.md). Do not open public issues for security problems.

## License

[Apache License 2.0](LICENSE) (see also [NOTICE](NOTICE))
