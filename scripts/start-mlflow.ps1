$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$port = if ($env:MLFLOW_PORT) { $env:MLFLOW_PORT } else { "5000" }
uv run mlflow server `
  --host 0.0.0.0 `
  --port $port `
  --backend-store-uri sqlite:///mlflow.db
