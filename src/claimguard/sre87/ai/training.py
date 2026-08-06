from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from claimguard.config import PROJECT_ROOT
from claimguard.mlops.tracking import (
    log_candidate_run,
    register_and_promote,
    resolve_tracking_settings,
)
from claimguard.sre87.ai.features import (
    CATEGORICAL_FEATURES,
    FEATURE_COLUMNS,
    NUMERIC_FEATURES,
)

DEFAULT_MODEL_PATH = PROJECT_ROOT / "artifacts" / "sre87_risk_model.joblib"
DEFAULT_METADATA_PATH = PROJECT_ROOT / "artifacts" / "sre87_risk_model_metadata.json"
DEFAULT_METRICS_PATH = PROJECT_ROOT / "artifacts" / "sre87_risk_metrics.json"


@dataclass(frozen=True)
class TrainingResult:
    selected_model: str
    metrics: dict[str, Any]
    model_path: Path
    metadata_path: Path
    metrics_path: Path
    mlflow: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected_model": self.selected_model,
            "metrics": self.metrics,
            "model_path": str(self.model_path),
            "metadata_path": str(self.metadata_path),
            "metrics_path": str(self.metrics_path),
            "mlflow": self.mlflow,
        }


def generate_training_frame(*, rows: int = 12_000, seed: int = 87) -> pd.DataFrame:
    if rows < 500:
        raise ValueError("rows must be at least 500")
    rng = np.random.default_rng(seed)
    statuses = rng.choice(
        [300, 655, 660, 665, 800, 850],
        rows,
        p=[0.16, 0.19, 0.06, 0.24, 0.18, 0.17],
    )
    age_hours = np.clip(rng.gamma(shape=2.3, scale=1.5, size=rows), 0.05, 12.0)
    claim_amount = np.clip(rng.lognormal(mean=7.25, sigma=0.85, size=rows), 25, 35_000)
    retry_count = np.clip(rng.poisson(lam=1.35, size=rows), 0, 8)
    queue_depth = np.clip(
        rng.gamma(shape=2.0, scale=110, size=rows),
        0,
        1_500,
    ).astype(int)
    endpoint_latency_ms = np.clip(rng.normal(loc=550, scale=290, size=rows), 40, 3_500)
    previous_failure_count = np.clip(rng.poisson(lam=0.65, size=rows), 0, 6)
    source_system = rng.choice(
        ["EDI", "PORTAL", "BATCH", "API"],
        rows,
        p=[0.48, 0.16, 0.24, 0.12],
    )
    provider_type = rng.choice(
        ["FACILITY", "PROFESSIONAL", "PHARMACY"],
        rows,
        p=[0.35, 0.55, 0.10],
    )

    status_weight = {
        300: -2.4,
        655: 0.45,
        660: 0.62,
        665: 0.86,
        800: 0.72,
        850: 0.93,
    }
    source_weight = {"EDI": 0.18, "PORTAL": -0.12, "BATCH": 0.31, "API": -0.08}
    provider_weight = {"FACILITY": 0.22, "PROFESSIONAL": 0.02, "PHARMACY": -0.15}

    linear = np.full(rows, -3.15)
    linear += np.array([status_weight[int(status)] for status in statuses])
    linear += np.maximum(age_hours - 1.5, 0) * 0.33
    linear += retry_count * 0.42
    linear += np.minimum(queue_depth / 250, 4.0) * 0.46
    linear += np.minimum(endpoint_latency_ms / 1_000, 3.0) * 0.38
    linear += previous_failure_count * 0.57
    linear += (claim_amount > 5_000) * 0.30
    linear += np.array([source_weight[str(value)] for value in source_system])
    linear += np.array([provider_weight[str(value)] for value in provider_type])
    linear += rng.normal(0, 0.55, rows)

    probability = 1.0 / (1.0 + np.exp(-linear))
    unresolved = rng.binomial(1, np.clip(probability, 0.01, 0.98))

    return pd.DataFrame(
        {
            "process_status": statuses.astype(float),
            "age_hours": age_hours,
            "claim_amount": claim_amount,
            "retry_count": retry_count.astype(float),
            "queue_depth": queue_depth.astype(float),
            "endpoint_latency_ms": endpoint_latency_ms,
            "previous_failure_count": previous_failure_count.astype(float),
            "source_system": source_system,
            "provider_type": provider_type,
            "will_remain_non_300": unresolved,
        }
    )


def _preprocessor() -> ColumnTransformer:
    numeric = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
        ]
    )
    categorical = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("one_hot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )
    return ColumnTransformer(
        transformers=[
            ("numeric", numeric, NUMERIC_FEATURES),
            ("categorical", categorical, CATEGORICAL_FEATURES),
        ]
    )


def _candidate_models(seed: int) -> dict[str, Any]:
    return {
        "logistic_regression": LogisticRegression(
            max_iter=1_000,
            class_weight="balanced",
            random_state=seed,
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=220,
            min_samples_leaf=4,
            class_weight="balanced_subsample",
            random_state=seed,
            n_jobs=-1,
        ),
    }


def _metrics(
    y_true: pd.Series,
    probability: np.ndarray,
    threshold: float = 0.5,
) -> dict[str, float]:
    predicted = (probability >= threshold).astype(int)
    recall = recall_score(y_true, predicted, zero_division=0)
    f1 = f1_score(y_true, predicted, zero_division=0)
    roc_auc = roc_auc_score(y_true, probability)
    selection_score = (0.55 * recall) + (0.30 * f1) + (0.15 * roc_auc)
    return {
        "accuracy": round(float(accuracy_score(y_true, predicted)), 6),
        "precision": round(
            float(precision_score(y_true, predicted, zero_division=0)),
            6,
        ),
        "recall": round(float(recall), 6),
        "f1": round(float(f1), 6),
        "roc_auc": round(float(roc_auc), 6),
        "decision_threshold": threshold,
        "selection_score": round(float(selection_score), 6),
    }


def train_risk_model(
    *,
    rows: int = 12_000,
    seed: int = 87,
    model_path: Path = DEFAULT_MODEL_PATH,
    metadata_path: Path = DEFAULT_METADATA_PATH,
    metrics_path: Path = DEFAULT_METRICS_PATH,
    enable_mlflow: bool = True,
    candidate_names: tuple[str, ...] = ("logistic_regression", "random_forest"),
) -> TrainingResult:
    frame = generate_training_frame(rows=rows, seed=seed)
    train_frame, test_frame = train_test_split(
        frame,
        test_size=0.22,
        random_state=seed,
        stratify=frame["will_remain_non_300"],
    )
    x_train = train_frame[FEATURE_COLUMNS]
    y_train = train_frame["will_remain_non_300"]
    x_test = test_frame[FEATURE_COLUMNS]
    y_test = test_frame["will_remain_non_300"]

    candidates = _candidate_models(seed)
    unknown = set(candidate_names) - set(candidates)
    if unknown:
        raise ValueError(f"Unknown candidate models: {sorted(unknown)}")

    evaluations: dict[str, dict[str, Any]] = {}
    pipelines: dict[str, Pipeline] = {}
    run_ids: dict[str, str] = {}
    settings = resolve_tracking_settings(
        experiment_name="ClaimGuard SRE87 Risk",
        registered_model_name="ClaimGuardSRE87RiskModel",
    )

    for model_name in candidate_names:
        estimator = candidates[model_name]
        pipeline = Pipeline(
            steps=[
                ("preprocess", _preprocessor()),
                ("classifier", estimator),
            ]
        )
        pipeline.fit(x_train, y_train)
        probability = pipeline.predict_proba(x_test)[:, 1]
        metrics = _metrics(y_test, probability)
        evaluations[model_name] = metrics
        pipelines[model_name] = pipeline
        if enable_mlflow:
            run_ids[model_name] = log_candidate_run(
                settings=settings,
                model_name=model_name,
                pipeline=pipeline,
                classifier_params=estimator.get_params(),
                metrics=metrics,
                dataset_rows=len(frame),
                positive_rate=float(frame["will_remain_non_300"].mean()),
                input_example=x_test.head(5),
            )

    selected_model = max(
        candidate_names,
        key=lambda name: (
            evaluations[name]["selection_score"],
            evaluations[name]["recall"],
            evaluations[name]["f1"],
        ),
    )
    selected_pipeline = pipelines[selected_model]
    selected_metrics = evaluations[selected_model]

    for output_path in (model_path, metadata_path, metrics_path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(selected_pipeline, model_path)
    metadata = {
        "model_name": selected_model,
        "model_version": "sre87-risk-0.1.0",
        "target": "will_remain_non_300",
        "advisory_only": True,
        "routing_authority": "deterministic_sre87_rules",
        "training_rows": len(frame),
        "positive_rate": round(float(frame["will_remain_non_300"].mean()), 6),
        "features": FEATURE_COLUMNS,
        "decision_threshold": selected_metrics["decision_threshold"],
        "selection_score": selected_metrics["selection_score"],
        "seed": seed,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    mlflow_result: dict[str, Any] | None = None
    if enable_mlflow:
        mlflow_result = register_and_promote(
            settings=settings,
            selected_run_id=run_ids[selected_model],
            selected_metrics=selected_metrics,
        )
        mlflow_result["candidate_run_ids"] = run_ids
        mlflow_result["selected_run_id"] = run_ids[selected_model]

    payload = {
        "selected_model": selected_model,
        "selected_metrics": selected_metrics,
        "candidates": evaluations,
        "metadata": metadata,
        "mlflow": mlflow_result,
    }
    metrics_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return TrainingResult(
        selected_model=selected_model,
        metrics=selected_metrics,
        model_path=model_path,
        metadata_path=metadata_path,
        metrics_path=metrics_path,
        mlflow=mlflow_result,
    )
