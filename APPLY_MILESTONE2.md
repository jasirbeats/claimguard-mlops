# Apply ClaimGuard Milestone 2

Extract this ZIP directly into the root of the existing `claimguard-mlops-mvp` repository and allow overwrites.

```bash
cd ~/AI/claimguard-mlops-mvp
unzip -o ~/Downloads/claimguard-mlops-milestone2-patch.zip -d .
chmod +x scripts/start-mlflow.sh scripts/run-mlflow-demo.sh
uv sync --dev
uv run pytest -v
uv run claimguard-train
./scripts/start-mlflow.sh
```

Open `http://127.0.0.1:5000` and inspect the **ClaimGuard AI** experiment and **ClaimGuardRiskModel** registry entry.
