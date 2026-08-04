from pathlib import Path

import joblib

from claimguard.data.generate import write_dataset
from claimguard.models.train import train


def test_training_creates_artifacts(tmp_path: Path) -> None:
    data = write_dataset(tmp_path / "claims.csv", rows=1_000, seed=19)
    model = tmp_path / "model.joblib"
    metrics = tmp_path / "metrics.json"
    metadata = tmp_path / "metadata.json"

    result = train(data, model, metrics, metadata)

    assert model.exists()
    assert metrics.exists()
    assert metadata.exists()
    assert result["selected_model"] in {"logistic_regression", "random_forest"}
    bundle = joblib.load(model)
    assert "model" in bundle
