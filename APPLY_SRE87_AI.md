# Apply the SRE 87 AI Risk-Scoring Patch

```bash
unzip -o ~/Downloads/claimguard-sre87-ai-risk-scoring-patch.zip -d /tmp/claimguard-sre87-ai
cp -a /tmp/claimguard-sre87-ai/claimguard-sre87-ai-risk-scoring-patch/. .
chmod +x scripts/run-sre87-ai-demo.sh
uv sync --all-extras --dev
uv run ruff check . --fix
uv run ruff format .
uv run pytest -q
```

Train and demonstrate:

```bash
uv run python -m claimguard.sre87.ai --rows 12000 --no-mlflow
uv run claimguard-sre87 seed --scenario happy
uv run claimguard-sre87 risk-preview
uv run claimguard-sre87 run
```
