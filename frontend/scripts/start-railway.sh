#!/usr/bin/env sh
set -eu

exec pnpm start -- --hostname 0.0.0.0 --port "${PORT:-3000}"
