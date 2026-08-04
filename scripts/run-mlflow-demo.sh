#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
uv sync --dev
uv run claimguard-generate --rows 10000 --seed 42
uv run claimguard-train
uv run pytest
printf '\nTracked training complete. Start the MLflow UI in another terminal:\n  ./scripts/start-mlflow.sh\n\nThen open:\n  http://127.0.0.1:5000\n'
