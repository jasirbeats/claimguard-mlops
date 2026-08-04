from pathlib import Path

from fastapi.testclient import TestClient

from claimguard.api.main import app
from claimguard.api.model_service import load_model_bundle
from claimguard.data.generate import write_dataset
from claimguard.models.train import train


def sample_request() -> dict[str, object]:
    return {
        "claim_tracking_id": "SYN-DEMO-0001",
        "claim_type": "professional",
        "state_code": "LA",
        "provider_type": "hospital",
        "source_system": "batch",
        "claim_amount": 8250.50,
        "retry_count": 3,
        "queue_depth": 240,
        "processing_duration_seconds": 12500,
        "previous_failure_count": 2,
        "hour_of_day": 2,
        "day_of_week": 1,
        "procedure_count": 8,
        "endpoint_response_code": "503",
    }


def test_predict_endpoint(tmp_path: Path, monkeypatch) -> None:
    data = write_dataset(tmp_path / "claims.csv", rows=1_000, seed=23)
    model_path = tmp_path / "model.joblib"
    train(
        data,
        model_path,
        tmp_path / "metrics.json",
        tmp_path / "metadata.json",
    )
    monkeypatch.setenv("CLAIMGUARD_MODEL_PATH", str(model_path))
    load_model_bundle.cache_clear()

    client = TestClient(app)
    response = client.post("/predict", json=sample_request())

    assert response.status_code == 200
    body = response.json()
    assert body["prediction"] in {"low_risk", "high_risk"}
    assert 0 <= body["failure_probability"] <= 1
