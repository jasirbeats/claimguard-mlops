from claimguard.mlops.tracking import default_tracking_uri, resolve_tracking_settings


def test_default_tracking_uses_sqlite() -> None:
    assert default_tracking_uri().startswith("sqlite:////")


def test_tracking_settings_allow_overrides() -> None:
    settings = resolve_tracking_settings(
        tracking_uri="sqlite:///test.db",
        experiment_name="test-experiment",
        registered_model_name="test-model",
    )
    assert settings.tracking_uri == "sqlite:///test.db"
    assert settings.experiment_name == "test-experiment"
    assert settings.registered_model_name == "test-model"
