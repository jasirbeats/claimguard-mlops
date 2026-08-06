.PHONY: install generate train train-local test lint run demo mlflow-demo mlflow-server docker-build docker-run compose-up compose-down traffic sre87-seed sre87-run sre87-demo sre87-unresolved sre87-failure clean

install:
	uv sync --dev

generate:
	uv run claimguard-generate --rows 10000 --seed 42

train:
	uv run claimguard-train

train-local:
	uv run claimguard-train --no-mlflow

test:
	uv run pytest --cov=claimguard --cov-report=term-missing

lint:
	uv run ruff check .
	uv run ruff format --check .

run:
	uv run uvicorn claimguard.api.main:app --reload

demo: generate train-local test

mlflow-demo:
	./scripts/run-mlflow-demo.sh

mlflow-server:
	./scripts/start-mlflow.sh

docker-build:
	docker build -t claimguard-ai:0.1.0 .

docker-run:
	docker run --rm -p 8000:8000 claimguard-ai:0.1.0

compose-up:
	docker compose up --build -d

compose-down:
	docker compose down

traffic:
	./scripts/generate-monitoring-traffic.sh 100

sre87-seed:
	uv run claimguard-sre87 seed --scenario happy

sre87-run:
	uv run claimguard-sre87 run

sre87-demo:
	./scripts/run-sre87-demo.sh happy

sre87-unresolved:
	./scripts/run-sre87-demo.sh unresolved

sre87-failure:
	./scripts/run-sre87-demo.sh endpoint-failure

clean:
	rm -rf .venv .pytest_cache .ruff_cache .coverage htmlcov
	rm -f data/raw/*.csv artifacts/*.joblib artifacts/*.json mlflow.db
	rm -rf mlartifacts runtime/sre87
	rm -f data/sre87/claims.json
