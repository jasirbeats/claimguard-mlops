from __future__ import annotations

import pandas as pd

from claimguard.config import ID_COLUMN, MODEL_FEATURES, TARGET_COLUMN


class DataValidationError(ValueError):
    """Raised when a dataset does not satisfy the training contract."""


def validate_training_data(df: pd.DataFrame) -> None:
    required = {ID_COLUMN, TARGET_COLUMN, *MODEL_FEATURES}
    missing = sorted(required.difference(df.columns))
    if missing:
        raise DataValidationError(f"Missing required columns: {missing}")

    if df.empty:
        raise DataValidationError("Training data is empty")

    if df[ID_COLUMN].duplicated().any():
        raise DataValidationError("claim_tracking_id values must be unique")

    target_values = set(df[TARGET_COLUMN].dropna().unique().tolist())
    if not target_values.issubset({0, 1}) or len(target_values) < 2:
        raise DataValidationError("Target must contain both binary classes 0 and 1")

    if df[MODEL_FEATURES].isna().mean().max() > 0.25:
        raise DataValidationError("At least one model feature contains more than 25% nulls")
