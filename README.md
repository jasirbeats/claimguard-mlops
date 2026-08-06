# ClaimGuard AI — MLOps Infrastructure Portfolio Project

ClaimGuard AI is a production-style portfolio project that predicts whether a synthetic claims-processing workflow will become stuck. It demonstrates data generation, validation, reproducible model training, model comparison, artifact persistence, API serving, tests, containerization, and CI.

> All records are synthetic. Do not add employer data, credentials, internal URLs, proprietary schemas, or protected health information.

## Current milestone

**Milestone 2: MLflow experiment tracking and model registry**

- Reproducible synthetic dataset
- Data-contract validation
- Logistic regression and random forest candidates
- Recall-weighted model selection
- Versioned model bundle and JSON metrics
- FastAPI inference service
- Liveness, readiness, and model-info endpoints
- Unit and integration tests
- MLflow experiment tracking for every candidate
- SQLite-backed model registry and aliases
- Champion/candidate promotion guardrails
- Dockerfile and GitHub Actions CI

## Architecture

```text
Synthetic Generator -> CSV -> Validation -> Training/Evaluation
                                             |
                                             v
                                  Trusted Model Artifact
                                             |
                                             v
                                    FastAPI /predict
```

## Prerequisites

- Python 3.11–3.13
- Git
- Recommended: `uv`
- Optional: Docker Desktop

## Setup with uv

### Windows PowerShell

```powershell
cd claimguard-mlops-mvp
powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"
.\scripts\run-demo.ps1
```

### macOS/Linux

```bash
cd claimguard-mlops-mvp
curl -LsSf https://astral.sh/uv/install.sh | sh
./scripts/run-demo.sh
```

## Manual workflow

```bash
uv sync --dev
uv run claimguard-generate --rows 10000 --seed 42
uv run claimguard-train
uv run pytest
uv run uvicorn claimguard.api.main:app --reload
```

Open the interactive API documentation at:

```text
http://127.0.0.1:8000/docs
```

## Test a prediction

### PowerShell

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/predict" `
  -ContentType "application/json" `
  -Body (Get-Content .\sample-request.json -Raw)
```

### macOS/Linux

```bash
curl -X POST "http://127.0.0.1:8000/predict" \
  -H "Content-Type: application/json" \
  --data @sample-request.json
```

## API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health/live` | Process liveness |
| GET | `/health/ready` | Model readiness |
| GET | `/model/info` | Deployed model metadata |
| POST | `/predict` | Risk prediction |

## Generated artifacts

After training:

```text
artifacts/model.joblib
artifacts/metrics.json
artifacts/model_metadata.json
```

`joblib` artifacts must only be loaded from trusted project builds. Model artifacts are environment-sensitive, so training and serving dependencies should remain synchronized.

## Docker

Train the model before building the image:

```bash
uv run claimguard-generate
uv run claimguard-train
docker build -t claimguard-ai:0.1.0 .
docker run --rm -p 8000:8000 claimguard-ai:0.1.0
```

## Interview story

“I built a reproducible classification pipeline that generates and validates synthetic operational data, compares candidate models, selects the winner using recall-weighted criteria, persists a versioned model artifact, and serves predictions through a validated FastAPI service. I added automated tests, container hardening basics, health endpoints, and CI to make the project operable rather than notebook-only.”

## Next milestones

1. MLflow experiment tracking and model registry
2. Prometheus metrics and Grafana dashboard
3. Docker Compose for API, MLflow, PostgreSQL, and MinIO
4. Kubernetes manifests, probes, autoscaling, and rollout controls
5. Drift detection and retraining workflow
6. Terraform and cloud deployment

## Milestone 2 — MLflow tracking and registry

Tracked training now creates one MLflow run for each candidate model, logs parameters and evaluation metrics, stores the model and evaluation report, registers the selected model, and manages these aliases:

- `candidate`: newest validated selected model
- `champion`: model currently approved for serving
- `rollback`: previous champion after a successful promotion

The first validated model becomes champion. Later candidates are promoted only when recall does not regress and the recall-weighted selection score improves.

### Run tracked training

```bash
uv sync --dev
uv run claimguard-generate --rows 10000 --seed 42
uv run claimguard-train
```

### Start the MLflow dashboard

```bash
./scripts/start-mlflow.sh
```

Open:

```text
http://127.0.0.1:5000
```

In the UI, open the **ClaimGuard AI** experiment to compare Logistic Regression and Random Forest. Open **Models** to inspect `ClaimGuardRiskModel` versions and aliases.

### Train without MLflow

Unit tests and lightweight local checks can bypass tracking:

```bash
uv run claimguard-train --no-mlflow
```

### Generated MLflow state

```text
mlflow.db       # SQLite tracking and registry metadata
mlartifacts/    # logged model and evaluation artifacts
```

Both paths are ignored by Git because experiment state and large artifacts should not be committed to the source repository.


## SRE 87 deterministic control-cycle digital twin

ClaimGuard now includes a synthetic implementation of the SRE 87 hourly claim-monitoring contract. It validates prior-run claim IDs before querying new work, halts when a previous claim has not reached status `300`, applies deterministic routing for statuses `655`, `665`, `800`, and `850`, writes audit artifacts, creates mock incidents, preserves exit codes, and supports pause/resume and dry-run controls.

```bash
uv run claimguard-sre87 seed --scenario happy
uv run claimguard-sre87 run
```

Demonstrate the mandatory prior-run halt:

```bash
uv run claimguard-sre87 seed --scenario unresolved
uv run claimguard-sre87 run
uv run claimguard-sre87 run
# second command exits 1 and writes one mock incident
```

See `docs/sre87-digital-twin.md` for the full requirement mapping and enterprise adapter boundaries.
