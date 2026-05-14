# GrillKit Project Rules

## Core Principles

### 1. Documentation-First Development

**Rule**: Every code change MUST include corresponding documentation updates.

- Update README.md if changing user-facing features
- Update design docs in `/docs/design/` if changing architecture
- Update API docs if changing endpoints
- Add docstrings to new public functions/classes

### 2. Follow the Plan

**Rule**: All development MUST follow the plans in `/docs/plans/`.

- Read the next plan file before starting work
- Implement exactly what is specified in the plan
- Ask for clarification if the plan is unclear
- Do not skip steps or add unplanned features

### 3. Clean Up Completed Work

**Rule**: After completing a plan step, REMOVE the corresponding plan file.

Example:
- After implementing Task 4 (SQLAlchemy models), delete `/docs/plans/04-sqlalchemy-models.md`
- This keeps the project clean and shows real progress

### 4. Project Structure Compliance

**Rule**: All code MUST follow the established project structure:

```
app/
├── ai/              # AI provider adapters only
├── api/             # FastAPI endpoints only
├── engine/          # Business logic only
├── main.py          # App factory
├── database.py      # DB connection
├── models.py        # SQLAlchemy models
└── questions.py     # YAML loader
data/                # Data files and config
templates/           # Jinja2 templates only
static/              # CSS/assets only
tests/               # Test files only
```

### 5. Code Quality Standards

**Rule**: All code MUST pass quality checks before commit.

```bash
# Before every commit:
ruff check --fix .    # Lint and auto-fix
ruff format .         # Format code
mypy .                # Type check
pytest                # Run tests
```

### 6. Commit Message Convention

**Rule**: Use conventional commits format.

```
feat(scope): description

- feat: new feature
- fix: bug fix
- docs: documentation
- refactor: code restructuring
- test: adding tests
- chore: maintenance
```

### 7. uv Package Management

**Rule**: Use `uv` for all Python operations.

```bash
# Add dependency
uv add <package>

# Add dev dependency
uv add --dev <package>

# Sync environment
uv sync --extra dev

# Run commands
uv run pytest
```

### 8. Docker-First Deployment

**Rule**: Application must always be runnable via docker-compose.

- Docker-compose is the PRIMARY deployment method
- Uvicorn directly is only for DEVELOPMENT
- Test docker-compose before committing changes

### 9. AI Provider Support

**Rule**: Support both cloud and local AI providers.

**Cloud**: OpenAI, Anthropic, Groq (require API key)
**Local**: Ollama, vLLM, llama.cpp (no API key needed)

### 10. Security Awareness

**Rule**: Never commit secrets or API keys.

- `data/config.json` is gitignored - store API keys there
- Use environment variables for sensitive data
- Report security issues via GitHub Security Advisory (not public issues)

## Workflow Checklist

Before starting work:
- [ ] Read next plan file from `/docs/plans/`
- [ ] Understand acceptance criteria
- [ ] Ask clarifying questions if needed

During development:
- [ ] Follow plan exactly
- [ ] Update documentation as you code
- [ ] Run quality checks (ruff, mypy, pytest)
- [ ] Test with docker-compose

After completing:
- [ ] Delete completed plan file
- [ ] Update CHANGELOG.md
- [ ] Verify all checks pass
- [ ] Commit with conventional message
