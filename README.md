# GrillKit - AI Interview Trainer

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-yellow.svg)](https://opensource.org/licenses/Apache-2.0)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688.svg)](https://fastapi.tiangolo.com)
[![Ruff](https://img.shields.io/badge/linter-ruff-261230.svg)](https://github.com/astral-sh/ruff)

Practice technical interviews with an AI interviewer. Open-source platform for developers to prepare for coding interviews.

> **Status**: Beta - Real-time AI interview engine with scoring and feedback.

## Current Features

- **Real-time AI Interview** - WebSocket-based chat with AI interviewer, answer evaluation, and follow-up questions
- **AI Scoring & Feedback** - Per-question scores (1-5), strengths/weaknesses, and final session evaluation
- **Follow-up Questions** - AI probes deeper on insufficient answers (up to 2 follow-ups per question)
- **Session Management** - Create, answer, and complete interview sessions with full history
- **Category Selection** - Choose interview topics and difficulty levels from YAML question bank
- **AI Provider Configuration** - Setup wizard for OpenAI-compatible APIs (OpenAI, Ollama, vLLM)
- **Connection Testing** - Validate API keys before saving
- **SQLite Database** - Persistent storage for sessions and answers

## In Progress

- **Interview History** - Browse past interviews with scores and filtering
- **Time Tracking** - Response time monitoring per question
- **Additional AI Providers** - Native Anthropic Claude support
- **More Languages** - Go, JavaScript, Java, C++, SQL question banks

## Planned

- **Code Editor** - Monaco integration with syntax highlighting
- **Advanced Features** - Voice interviews, custom question banks
- **Standalone Frontend** - React/Vue SPA (seeking contributors)
- **PWA Support** - Offline interview practice

## Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/)
- API key from your preferred AI provider (optional for local models like Ollama)

### Run with Docker

```bash
# Clone the repository
git clone https://github.com/yourusername/grillkit.git
cd grillkit

# Start the application
docker-compose up --build

# Open in browser
# http://localhost:8000
```

### Development Setup

```bash
# Install dependencies
uv sync --extra dev

# Activate virtual environment
source .venv/bin/activate

# Run the application
uvicorn app.main:app --reload
```

### First Run Setup

1. Open `http://localhost:8000` in your browser
2. Complete the setup wizard:
   - **OpenAI-compatible providers**: (e.g., OpenAI, Ollama, vLLM)
   - Enter base URL and model name
   - Test connection before saving
3. Configuration is stored in `data/config.json` (gitignored)

## Configuration

Supported providers (OpenAI-compatible):
- OpenAI (`https://api.openai.com/v1`)
- Ollama (`http://localhost:11434/v1`)
- Any other OpenAI-compatible endpoint

## Project Structure

```
app/
├── ai/              # AI provider adapters (base, factory, openai-compatible)
├── api/             # API endpoints (config, interview, root, setup)
├── services/        # Business logic (config, interview session, evaluator)
├── database.py      # SQLAlchemy database connection
├── main.py          # FastAPI app factory
├── models.py        # SQLAlchemy models (InterviewSession, Answer)
└── questions.py     # YAML question loader
data/
├── questions/       # YAML question banks
│   └── python/
│       ├── junior/
│       ├── middle/
│       └── senior/
├── config.json      # User configuration (gitignored)
└── db/              # SQLite database directory (gitignored)
templates/           # Jinja2 HTML templates
static/              # CSS and assets
tests/               # Test suite
docs/                # Design documents
ARCHITECTURE.md      # Full architecture specification
```

## Development

### Running Tests

```bash
pytest
```

### Code Quality

```bash
# Format and lint
ruff check --fix .
ruff format .

# Type check
mypy .
```

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

Priority areas:
- Interview engine (WebSocket chat implementation)
- Additional programming languages (YAML question banks)
- Frontend improvements (HTMX or React/Vue SPA)
- AI provider integrations

## Security

If you discover a security issue, please see [SECURITY.md](SECURITY.md) for responsible disclosure.

## License

This project is licensed under the [Apache License 2.0](LICENSE).

## Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- AI providers: [OpenAI](https://openai.com/), [Ollama](https://ollama.com/)
