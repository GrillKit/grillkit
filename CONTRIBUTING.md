# Contributing to GrillKit

Thank you for your interest in contributing to GrillKit! We welcome contributions from the community.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/yourusername/grillkit.git`
3. Create a branch: `git checkout -b feature/your-feature-name`

## Development Setup

```bash
# Install dependencies
uv sync --extra dev

# Activate virtual environment
source .venv/bin/activate

# Run tests
pytest

# Run the application
uvicorn app.main:app --reload
```

## How to Contribute

### Reporting Bugs

- Check if the issue already exists
- Provide clear steps to reproduce
- Include Python version and OS information
- Add relevant logs or screenshots

### Suggesting Features

- Open an issue with the "feature request" label
- Describe the feature and its use case
- Discuss implementation approach

### Adding Questions

Interview questions are stored in YAML format:

```yaml
# data/questions/python/junior/data_structures.yaml
questions:
  - id: "ds-001"
    type: "knowledge"  # knowledge | coding | scenario | debugging
    difficulty: 1      # 1-5 scale within level
    tags: ["list", "tuple"]
    question:
      text: "What's the difference between a list and a tuple?"
      code: null
    follow_ups:
      - "When would you choose a tuple over a list?"
    expected_points:
      - "Mutability: lists mutable, tuples immutable"
```

Guidelines:
- Use clear, concise language
- Include time estimates (in minutes)
- Tag appropriately by category and difficulty
- Test your YAML syntax

### Code Contributions

1. **Write tests** for new features
2. **Follow existing code style** (ruff format, ruff check)
3. **Update documentation** if needed
4. **Keep commits atomic** and well-described

## Code Standards

### Python Style

- Format with `ruff format` (line length: 88)
- Lint with `ruff check`
- Type check with `mypy --strict`
- Use type hints everywhere

### Commit Messages

Use [conventional commits](https://www.conventionalcommits.org/):
```
feat(engine): add new interview category
fix(api): resolve time tracking bug
docs: update README
refactor(questions): simplify question loader
test(session): add session manager tests
chore: update dependencies
```

## Pull Request Process

1. Update your branch with latest `main`
2. Ensure all tests pass
3. Update relevant documentation
4. Fill out the PR template completely
5. Request review from maintainers

## Code of Conduct

Please read and follow our [Code of Conduct](CODE_OF_CONDUCT.md).

## Questions?

- Open a [Discussion](https://github.com/yourusername/grillkit/discussions)
- Open an issue with the "question" label

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.
