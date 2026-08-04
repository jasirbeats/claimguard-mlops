$ErrorActionPreference = "Stop"
uv sync --dev
uv run claimguard-generate --rows 10000 --seed 42
uv run claimguard-train
uv run pytest
Write-Host "`nDemo assets are ready. Start the API with:"
Write-Host "  uv run uvicorn claimguard.api.main:app --reload"
