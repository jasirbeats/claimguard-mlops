#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PORT="${MLFLOW_PORT:-5000}"
exec uv run mlflow server \
  --host 0.0.0.0 \
  --port "$PORT" \
  --backend-store-uri sqlite:///mlflow.db
