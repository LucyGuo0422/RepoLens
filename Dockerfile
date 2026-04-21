FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY pyproject.toml uv.lock ./
COPY api/ ./api/

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8002

CMD ["uvicorn", "api.api:app", "--host", "0.0.0.0", "--port", "8002"]
