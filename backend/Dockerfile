FROM node:24-bookworm-slim AS node

FROM python:3.13-slim

ARG UV_VERSION=0.9.18

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules

RUN ln -sf /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -sf /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

RUN pip install --no-cache-dir uv==${UV_VERSION}
RUN npm install -g @anthropic-ai/claude-code

# 创建非 root 用户
RUN useradd -m -u 1000 appuser

WORKDIR /app/backend

COPY backend/pyproject.toml backend/uv.lock ./

RUN uv sync --group dev --frozen && \
    chown -R appuser:appuser /app

# 切换到非 root 用户
USER appuser

CMD ["sh", "-c", "uv sync --group dev --frozen && uv run alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"]
