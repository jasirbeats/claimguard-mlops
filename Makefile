.PHONY: install generate train train-local test lint run demo mlflow-demo mlflow-server docker-build docker-run clean

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

clean:
	rm -rf .venv .pytest_cache .ruff_cache .coverage htmlcov
	rm -f data/raw/*.csv artifacts/*.joblib artifacts/*.json mlflow.db
	rm -rf mlartifacts
