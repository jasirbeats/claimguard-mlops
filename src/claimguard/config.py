from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_PATH = PROJECT_ROOT / "data" / "raw" / "synthetic_claims.csv"
DEFAULT_MODEL_PATH = PROJECT_ROOT / "artifacts" / "model.joblib"
DEFAULT_METRICS_PATH = PROJECT_ROOT / "artifacts" / "metrics.json"
DEFAULT_METADATA_PATH = PROJECT_ROOT / "artifacts" / "model_metadata.json"

TARGET_COLUMN = "will_become_stuck"
ID_COLUMN = "claim_tracking_id"

CATEGORICAL_FEATURES = [
    "claim_type",
    "state_code",
    "provider_type",
    "source_system",
    "endpoint_response_code",
]

NUMERIC_FEATURES = [
    "claim_amount",
    "retry_count",
    "queue_depth",
    "processing_duration_seconds",
    "previous_failure_count",
    "hour_of_day",
    "day_of_week",
    "procedure_count",
]

MODEL_FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES
