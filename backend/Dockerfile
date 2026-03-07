FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs npm \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv
RUN npm install -g @anthropic-ai/claude-code

WORKDIR /app/backend

COPY backend/pyproject.toml backend/uv.lock ./

RUN uv sync --extra dev --frozen

CMD ["sh", "-c", "uv sync --extra dev && uv run alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"]
