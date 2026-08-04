import pytest

from claimguard.data.generate import generate_claims
from claimguard.data.validate import DataValidationError, validate_training_data


def test_valid_dataset_passes() -> None:
    validate_training_data(generate_claims(rows=250, seed=11))


def test_missing_feature_fails() -> None:
    df = generate_claims(rows=250, seed=11).drop(columns=["queue_depth"])
    with pytest.raises(DataValidationError, match="Missing required columns"):
        validate_training_data(df)
