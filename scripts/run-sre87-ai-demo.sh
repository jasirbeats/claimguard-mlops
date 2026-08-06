#!/usr/bin/env bash
set -euo pipefail

ROWS="${1:-12000}"

uv run python -m claimguard.sre87.ai --rows "$ROWS" --no-mlflow
uv run claimguard-sre87 seed --scenario happy
uv run claimguard-sre87 risk-model-info
uv run claimguard-sre87 risk-preview
uv run claimguard-sre87 run
