from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from claimguard.config import DEFAULT_MODEL_PATH, MODEL_FEATURES


class ModelUnavailableError(RuntimeError):
    """Raised when the trained model artifact cannot be loaded."""


def configured_model_path() -> Path:
    return Path(os.getenv("CLAIMGUARD_MODEL_PATH", str(DEFAULT_MODEL_PATH)))


@lru_cache(maxsize=1)
def load_model_bundle() -> dict[str, Any]:
    path = configured_model_path()
    if not path.exists():
        raise ModelUnavailableError(
            f"Model artifact not found at {path}. Run the training command first."
        )
    # Only load artifacts created and trusted by this project.
    bundle = joblib.load(path)
    required = {"model", "model_name", "model_version", "threshold", "features"}
    if not required.issubset(bundle):
        raise ModelUnavailableError("Model artifact is missing required metadata")
    return bundle


def predict(payload: dict[str, Any]) -> dict[str, Any]:
    bundle = load_model_bundle()
    features = pd.DataFrame([{name: payload[name] for name in MODEL_FEATURES}])
    probability = float(bundle["model"].predict_proba(features)[0, 1])
    threshold = float(bundle["threshold"])
    return {
        "claim_tracking_id": payload["claim_tracking_id"],
        "prediction": "high_risk" if probability >= threshold else "low_risk",
        "failure_probability": round(probability, 6),
        "model_name": bundle["model_name"],
        "model_version": bundle["model_version"],
        "threshold": threshold,
    }
