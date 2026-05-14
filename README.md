# GrillKit - AI Interview Trainer

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-yellow.svg)](https://opensource.org/licenses/Apache-2.0)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688.svg)](https://fastapi.tiangolo.com)
[![Ruff](https://img.shields.io/badge/linter-ruff-261230.svg)](https://github.com/astral-sh/ruff)

Practice technical interviews with an AI interviewer. Open-source platform for developers to prepare for coding interviews.

> **Status**: MVP - Configuration and provider management ready. Interview engine in development.

## Current Features

- **AI Provider Configuration** - Setup wizard for OpenAI-compatible APIs (OpenAI, Ollama, vLLM)
- **Connection Testing** - Validate API keys before saving

## In Progress


- **Interview Engine** - WebSocket-based chat with AI interviewer
- **Time Tracking** - Response time monitoring per question
- **Feedback System** - AI-generated scoring and recommendations
- **Interview History** - Browse past interviews with scores
- **Category Selection** - Choose interview topics and difficulty
- **SQLite Database** - Interview storage schema ready
- **YAML Question Bank** - Python junior questions included

## Planned

- **Additional AI Providers** - Native Anthropic Claude support
- **More Languages** - Go, JavaScript, Java, C++, SQL question banks
- **Code Editor** - Monaco integration with syntax highlighting
- **Advanced Features** - Voice interviews, custom question banks
- **Standalone Frontend** - React/Vue SPA (seeking contributors)

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
├── api/             # API endpoints (root, config)
├── services/        # Business logic (config service)
├── database.py      # SQLAlchemy models and database
├── main.py          # FastAPI app factory
└── questions.py     # YAML question loader
data/
├── questions/       # YAML question banks
│   └── python/
│       └── junior/
├── config.json      # User configuration (gitignored)
└── grillkit.db      # SQLite database (gitignored)
templates/           # Jinja2 HTML templates
static/              # CSS and assets
tests/               # Test suite
docs/                # Design documents
design.md            # Full architecture specification
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
