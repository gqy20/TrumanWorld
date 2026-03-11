#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   1. Fill the variables below
#   2. Run from repo root: bash scripts/railway-bootstrap.sh
#
# This script assumes:
# - You already installed Railway CLI
# - You have logged in with `railway login`
# - You want three Railway services: backend, frontend, postgres
# - You may have a repo-root .env file; explicit shell vars override it

PROJECT_NAME="${PROJECT_NAME:-TrumanWorld}"
BACKEND_SERVICE="${BACKEND_SERVICE:-backend}"
FRONTEND_SERVICE="${FRONTEND_SERVICE:-frontend}"
POSTGRES_SERVICE="${POSTGRES_SERVICE:-Postgres}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env}"

FRONTEND_DOMAIN="${FRONTEND_DOMAIN:-}"
ENABLE_CLAUDE="${ENABLE_CLAUDE:-}"

TRUMANWORLD_APP_ENV="${TRUMANWORLD_APP_ENV:-}"
TRUMANWORLD_LOG_LEVEL="${TRUMANWORLD_LOG_LEVEL:-}"
TRUMANWORLD_AGENT_PROVIDER="${TRUMANWORLD_AGENT_PROVIDER:-}"
TRUMANWORLD_DATABASE_URL="${TRUMANWORLD_DATABASE_URL:-}"
TRUMANWORLD_REDIS_URL="${TRUMANWORLD_REDIS_URL:-}"
TRUMANWORLD_ANTHROPIC_API_KEY="${TRUMANWORLD_ANTHROPIC_API_KEY:-}"
TRUMANWORLD_AGENT_MODEL="${TRUMANWORLD_AGENT_MODEL:-}"
TRUMANWORLD_DIRECTOR_AGENT_ENABLED="${TRUMANWORLD_DIRECTOR_AGENT_ENABLED:-}"
TRUMANWORLD_DIRECTOR_AGENT_MODEL="${TRUMANWORLD_DIRECTOR_AGENT_MODEL:-}"
INTERNAL_API_BASE_URL="${INTERNAL_API_BASE_URL:-}"
NEXT_PUBLIC_API_BASE_URL="${NEXT_PUBLIC_API_BASE_URL:-}"

load_env_file() {
  local env_file="$1"
  [[ -f "$env_file" ]] || return 0

  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    [[ -z "$line" ]] && continue
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ "$line" != *=* ]] && continue

    local key="${line%%=*}"
    local value="${line#*=}"

    key="$(printf '%s' "$key" | xargs)"

    if [[ "$value" =~ ^\".*\"$ ]] || [[ "$value" =~ ^\'.*\'$ ]]; then
      value="${value:1:${#value}-2}"
    fi

    if [[ -z "${!key:-}" ]]; then
      export "$key=$value"
    fi
  done < "$env_file"
}

require_value() {
  local name="$1"
  local value="$2"
  if [[ -z "$value" ]]; then
    echo "Missing required value: $name" >&2
    exit 1
  fi
}

echo "==> Loading .env defaults"
load_env_file "$ENV_FILE"

TRUMANWORLD_APP_ENV="${TRUMANWORLD_APP_ENV:-production}"
TRUMANWORLD_LOG_LEVEL="${TRUMANWORLD_LOG_LEVEL:-INFO}"
TRUMANWORLD_AGENT_PROVIDER="${TRUMANWORLD_AGENT_PROVIDER:-heuristic}"
TRUMANWORLD_DATABASE_URL="${TRUMANWORLD_DATABASE_URL:-\${{Postgres.DATABASE_URL}}}"
TRUMANWORLD_DIRECTOR_AGENT_ENABLED="${TRUMANWORLD_DIRECTOR_AGENT_ENABLED:-false}"
TRUMANWORLD_AGENT_MODEL="${TRUMANWORLD_AGENT_MODEL:-}"
TRUMANWORLD_DIRECTOR_AGENT_MODEL="${TRUMANWORLD_DIRECTOR_AGENT_MODEL:-}"
TRUMANWORLD_ANTHROPIC_API_KEY="${TRUMANWORLD_ANTHROPIC_API_KEY:-}"
INTERNAL_API_BASE_URL="${INTERNAL_API_BASE_URL:-http://backend.railway.internal/api}"
NEXT_PUBLIC_API_BASE_URL="${NEXT_PUBLIC_API_BASE_URL:-}"

if [[ -z "$ENABLE_CLAUDE" ]]; then
  if [[ "$TRUMANWORLD_AGENT_PROVIDER" == "claude" || "$TRUMANWORLD_AGENT_PROVIDER" == "anthropic" ]]; then
    ENABLE_CLAUDE="true"
  else
    ENABLE_CLAUDE="false"
  fi
fi

echo "==> Initializing Railway project"
railway init -n "$PROJECT_NAME" || true

echo "==> Creating services if needed"
railway add --service "$BACKEND_SERVICE" || true
railway add --service "$FRONTEND_SERVICE" || true
railway add --database postgres || true

echo "==> Setting backend base variables"
railway variable set --service "$BACKEND_SERVICE" \
  TRUMANWORLD_APP_ENV="$TRUMANWORLD_APP_ENV" \
  TRUMANWORLD_LOG_LEVEL="$TRUMANWORLD_LOG_LEVEL" \
  TRUMANWORLD_DATABASE_URL="$TRUMANWORLD_DATABASE_URL"

require_value "FRONTEND_DOMAIN" "$FRONTEND_DOMAIN"

echo "==> Setting backend CORS"
railway variable set --service "$BACKEND_SERVICE" \
  "TRUMANWORLD_CORS_ALLOWED_ORIGINS=[\"https://${FRONTEND_DOMAIN}\"]"

if [[ "$ENABLE_CLAUDE" == "true" ]]; then
  require_value "TRUMANWORLD_ANTHROPIC_API_KEY" "$TRUMANWORLD_ANTHROPIC_API_KEY"
  require_value "TRUMANWORLD_AGENT_MODEL" "$TRUMANWORLD_AGENT_MODEL"
  require_value "TRUMANWORLD_DIRECTOR_AGENT_MODEL" "$TRUMANWORLD_DIRECTOR_AGENT_MODEL"

  echo "==> Setting backend Claude variables"
  railway variable set --service "$BACKEND_SERVICE" \
    TRUMANWORLD_AGENT_PROVIDER=claude \
    TRUMANWORLD_AGENT_MODEL="$TRUMANWORLD_AGENT_MODEL" \
    TRUMANWORLD_DIRECTOR_AGENT_ENABLED=true \
    TRUMANWORLD_DIRECTOR_AGENT_MODEL="$TRUMANWORLD_DIRECTOR_AGENT_MODEL"

  printf '%s' "$TRUMANWORLD_ANTHROPIC_API_KEY" | railway variable set --service "$BACKEND_SERVICE" TRUMANWORLD_ANTHROPIC_API_KEY --stdin
else
  echo "==> Setting backend heuristic mode"
  railway variable set --service "$BACKEND_SERVICE" \
    TRUMANWORLD_AGENT_PROVIDER=heuristic \
    TRUMANWORLD_DIRECTOR_AGENT_ENABLED=false
fi

echo "==> Setting frontend variables"
railway variable set --service "$FRONTEND_SERVICE" \
  INTERNAL_API_BASE_URL="$INTERNAL_API_BASE_URL" \
  NEXT_PUBLIC_API_BASE_URL="$NEXT_PUBLIC_API_BASE_URL"

cat <<'EOF'

Next manual steps in Railway dashboard:

backend:
  Root Directory: backend
  Config File: /backend/railway.toml

frontend:
  Root Directory: frontend
  Config File: /frontend/railway.toml

Fallback if you do not use Config File:
  backend Build Command: uv sync --frozen
  backend Start Command: sh scripts/start-railway.sh
  frontend Build Command: npm ci && npm run build
  frontend Start Command: sh scripts/start-railway.sh

Then deploy:
  railway up --service backend
  railway up --service frontend

Useful checks:
  railway logs --service backend
  railway logs --service frontend
  railway status
EOF
