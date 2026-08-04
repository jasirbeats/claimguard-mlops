#!/usr/bin/env bash
set -euo pipefail
uv sync --dev
uv run claimguard-generate --rows 10000 --seed 42
uv run claimguard-train
uv run pytest
printf '\nDemo assets are ready. Start the API with:\n  uv run uvicorn claimguard.api.main:app --reload\n'
