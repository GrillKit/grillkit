# syntax=docker/dockerfile:1

# ------------------------------------------------------------------------------
# Builder: resolve and install production dependencies with uv
# ------------------------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app
COPY data/questions ./data/questions
COPY templates ./templates
COPY static ./static

RUN uv sync --frozen --no-dev

# ------------------------------------------------------------------------------
# Runtime: minimal image with app code and virtualenv from builder
# ------------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

RUN apt-get update \
    && apt-get install -y --no-install-recommends gosu \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /app/data/db

COPY --from=builder --chown=root:root /app/.venv /app/.venv
COPY --from=builder --chown=root:root /app/app /app/app
COPY --from=builder --chown=root:root /app/data/questions /app/data/questions
COPY --from=builder --chown=root:root /app/templates /app/templates
COPY --from=builder --chown=root:root /app/static /app/static
COPY alembic.ini /app/alembic.ini
COPY alembic /app/alembic

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["docker-entrypoint.sh"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
