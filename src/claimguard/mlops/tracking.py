from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from claimguard.config import PROJECT_ROOT

DEFAULT_EXPERIMENT_NAME = "ClaimGuard AI"
DEFAULT_REGISTERED_MODEL_NAME = "ClaimGuardRiskModel"
DEFAULT_MLFLOW_DB_PATH = PROJECT_ROOT / "mlflow.db"
DEFAULT_MLFLOW_ARTIFACT_ROOT = PROJECT_ROOT / "mlartifacts"


@dataclass(frozen=True)
class TrackingSettings:
    tracking_uri: str
    experiment_name: str
    registered_model_name: str
    artifact_root: Path


def default_tracking_uri() -> str:
    """Return an absolute SQLite URI that works from any current directory."""
    return f"sqlite:///{DEFAULT_MLFLOW_DB_PATH.resolve().as_posix()}"


def resolve_tracking_settings(
    tracking_uri: str | None = None,
    experiment_name: str | None = None,
    registered_model_name: str | None = None,
) -> TrackingSettings:
    return TrackingSettings(
        tracking_uri=tracking_uri or os.getenv("MLFLOW_TRACKING_URI") or default_tracking_uri(),
        experiment_name=experiment_name
        or os.getenv("MLFLOW_EXPERIMENT_NAME")
        or DEFAULT_EXPERIMENT_NAME,
        registered_model_name=registered_model_name
        or os.getenv("MLFLOW_REGISTERED_MODEL_NAME")
        or DEFAULT_REGISTERED_MODEL_NAME,
        artifact_root=Path(
            os.getenv("MLFLOW_ARTIFACT_ROOT", str(DEFAULT_MLFLOW_ARTIFACT_ROOT))
        ).resolve(),
    )


def _scalar_params(params: dict[str, Any]) -> dict[str, Any]:
    """Keep MLflow parameters concise and serializable."""
    allowed = (str, int, float, bool, type(None))
    return {key: value for key, value in params.items() if isinstance(value, allowed)}


def _uses_tracking_server(tracking_uri: str) -> bool:
    """Return True when MLflow is accessed through an HTTP tracking server."""
    return tracking_uri.startswith(("http://", "https://"))


def configure_tracking(settings: TrackingSettings) -> tuple[Any, str]:
    """Configure MLflow and return its client plus the experiment ID."""
    try:
        import mlflow
        from mlflow.tracking import MlflowClient
    except ImportError as exc:  # pragma: no cover - exercised only without optional runtime dep
        raise RuntimeError(
            "MLflow is not installed. Run 'uv sync --dev' before tracked training."
        ) from exc

    uses_server = _uses_tracking_server(settings.tracking_uri)
    if not uses_server:
        settings.artifact_root.mkdir(parents=True, exist_ok=True)

    mlflow.set_tracking_uri(settings.tracking_uri)
    client = MlflowClient(tracking_uri=settings.tracking_uri)
    experiment = client.get_experiment_by_name(settings.experiment_name)
    if experiment is None:
        create_kwargs: dict[str, Any] = {
            "tags": {
                "project": "claimguard-ai",
                "data_classification": "synthetic",
            }
        }
        if not uses_server:
            create_kwargs["artifact_location"] = settings.artifact_root.as_uri()

        experiment_id = client.create_experiment(
            settings.experiment_name,
            **create_kwargs,
        )
    else:
        experiment_id = experiment.experiment_id
    mlflow.set_experiment(settings.experiment_name)
    return client, experiment_id


def log_candidate_run(
    *,
    settings: TrackingSettings,
    model_name: str,
    pipeline: Any,
    classifier_params: dict[str, Any],
    metrics: dict[str, Any],
    dataset_rows: int,
    positive_rate: float,
    input_example: pd.DataFrame,
) -> str:
    """Log one model candidate and return its MLflow run ID."""
    import mlflow
    import mlflow.sklearn
    from mlflow.models import infer_signature

    configure_tracking(settings)
    metric_values = {
        key: float(value)
        for key, value in metrics.items()
        if key != "confusion_matrix" and isinstance(value, (int, float))
    }
    predictions = pipeline.predict(input_example)
    signature = infer_signature(input_example, predictions)

    with mlflow.start_run(run_name=model_name) as run:
        mlflow.set_tags(
            {
                "project": "claimguard-ai",
                "candidate_model": model_name,
                "data_classification": "synthetic",
                "workflow": "training",
            }
        )
        mlflow.log_params(
            {
                "model_name": model_name,
                "decision_threshold": metrics.get("decision_threshold", 0.5),
                "dataset_rows": dataset_rows,
                **_scalar_params(classifier_params),
            }
        )
        mlflow.log_metrics(
            {
                **metric_values,
                "positive_rate": float(positive_rate),
            }
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            report_path = Path(temp_dir) / "evaluation.json"
            report_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
            mlflow.log_artifact(str(report_path), artifact_path="evaluation")

        # MLflow 3 recommends `name`; the resulting model remains addressable by
        # the run-relative path used below for registry creation.
        mlflow.sklearn.log_model(
            sk_model=pipeline,
            name="model",
            signature=signature,
            input_example=input_example,
            metadata={"project": "ClaimGuard AI", "candidate": model_name},
            serialization_format="cloudpickle",
        )
        return run.info.run_id


def register_and_promote(
    *,
    settings: TrackingSettings,
    selected_run_id: str,
    selected_metrics: dict[str, Any],
) -> dict[str, Any]:
    """Register the selected run and promote it when it beats the champion."""
    import mlflow
    from mlflow.exceptions import MlflowException
    from mlflow.tracking import MlflowClient

    mlflow.set_tracking_uri(settings.tracking_uri)
    client = MlflowClient(tracking_uri=settings.tracking_uri)
    model_uri = f"runs:/{selected_run_id}/model"
    registered = mlflow.register_model(model_uri, settings.registered_model_name)
    version = str(registered.version)

    client.set_registered_model_alias(settings.registered_model_name, "candidate", version)
    client.set_model_version_tag(
        settings.registered_model_name,
        version,
        "validation_status",
        "passed",
    )

    promoted = False
    previous_champion_version: str | None = None
    promotion_reason: str

    try:
        champion = client.get_model_version_by_alias(
            settings.registered_model_name,
            "champion",
        )
        previous_champion_version = str(champion.version)
        champion_run = client.get_run(champion.run_id)
        champion_recall = float(champion_run.data.metrics.get("recall", 0.0))
        champion_score = float(champion_run.data.metrics.get("selection_score", 0.0))
        candidate_recall = float(selected_metrics["recall"])
        candidate_score = float(selected_metrics["selection_score"])

        if candidate_recall >= champion_recall and candidate_score > champion_score:
            client.set_registered_model_alias(
                settings.registered_model_name,
                "rollback",
                previous_champion_version,
            )
            client.set_registered_model_alias(
                settings.registered_model_name,
                "champion",
                version,
            )
            promoted = True
            promotion_reason = "Candidate met recall guardrail and improved selection score."
        else:
            promotion_reason = "Candidate did not outperform the current champion guardrails."
    except MlflowException:
        client.set_registered_model_alias(
            settings.registered_model_name,
            "champion",
            version,
        )
        promoted = True
        promotion_reason = "No champion existed, so the first validated model was promoted."

    client.set_model_version_tag(
        settings.registered_model_name,
        version,
        "promotion_status",
        "champion" if promoted else "candidate_only",
    )

    return {
        "tracking_uri": settings.tracking_uri,
        "experiment_name": settings.experiment_name,
        "registered_model_name": settings.registered_model_name,
        "registered_version": version,
        "candidate_alias": version,
        "champion_version": version if promoted else previous_champion_version,
        "previous_champion_version": previous_champion_version,
        "promoted_to_champion": promoted,
        "promotion_reason": promotion_reason,
    }
