from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from claimguard.config import (
    CATEGORICAL_FEATURES,
    DEFAULT_DATA_PATH,
    DEFAULT_METADATA_PATH,
    DEFAULT_METRICS_PATH,
    DEFAULT_MODEL_PATH,
    MODEL_FEATURES,
    NUMERIC_FEATURES,
    TARGET_COLUMN,
)
from claimguard.data.validate import validate_training_data

RANDOM_STATE = 42
DECISION_THRESHOLD = 0.50


def make_preprocessor() -> ColumnTransformer:
    numeric = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    categorical = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )
    return ColumnTransformer(
        transformers=[
            ("numeric", numeric, NUMERIC_FEATURES),
            ("categorical", categorical, CATEGORICAL_FEATURES),
        ]
    )


def candidate_models() -> dict[str, Any]:
    return {
        "logistic_regression": LogisticRegression(
            max_iter=1_000,
            class_weight="balanced",
            random_state=RANDOM_STATE,
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=220,
            max_depth=14,
            min_samples_leaf=3,
            class_weight="balanced_subsample",
            n_jobs=-1,
            random_state=RANDOM_STATE,
        ),
    }


def evaluate(y_true: pd.Series, probabilities: Any, threshold: float) -> dict[str, Any]:
    predictions = (probabilities >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, predictions, labels=[0, 1]).ravel()
    return {
        "accuracy": round(float(accuracy_score(y_true, predictions)), 6),
        "precision": round(float(precision_score(y_true, predictions, zero_division=0)), 6),
        "recall": round(float(recall_score(y_true, predictions, zero_division=0)), 6),
        "f1": round(float(f1_score(y_true, predictions, zero_division=0)), 6),
        "roc_auc": round(float(roc_auc_score(y_true, probabilities)), 6),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    }


def selection_score(metrics: dict[str, Any]) -> float:
    """Favor recall while retaining balanced overall performance."""
    return 0.60 * metrics["recall"] + 0.40 * metrics["f1"]


def train(
    data_path: Path = DEFAULT_DATA_PATH,
    model_path: Path = DEFAULT_MODEL_PATH,
    metrics_path: Path = DEFAULT_METRICS_PATH,
    metadata_path: Path = DEFAULT_METADATA_PATH,
) -> dict[str, Any]:
    df = pd.read_csv(data_path)
    validate_training_data(df)

    X = df[MODEL_FEATURES]
    y = df[TARGET_COLUMN].astype(int)
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.20,
        random_state=RANDOM_STATE,
        stratify=y,
    )

    results: dict[str, Any] = {}
    fitted_models: dict[str, Pipeline] = {}

    for name, classifier in candidate_models().items():
        pipeline = Pipeline(
            steps=[
                ("preprocessor", make_preprocessor()),
                ("classifier", classifier),
            ]
        )
        pipeline.fit(X_train, y_train)
        probabilities = pipeline.predict_proba(X_test)[:, 1]
        metrics = evaluate(y_test, probabilities, DECISION_THRESHOLD)
        metrics["selection_score"] = round(selection_score(metrics), 6)
        results[name] = metrics
        fitted_models[name] = pipeline

    selected_name = max(results, key=lambda name: results[name]["selection_score"])
    selected_model = fitted_models[selected_name]
    trained_at = datetime.now(UTC).isoformat()

    bundle = {
        "model": selected_model,
        "model_name": selected_name,
        "model_version": "0.1.0",
        "trained_at": trained_at,
        "threshold": DECISION_THRESHOLD,
        "features": MODEL_FEATURES,
    }

    for path in (model_path, metrics_path, metadata_path):
        path.parent.mkdir(parents=True, exist_ok=True)

    joblib.dump(bundle, model_path)

    metrics_payload = {
        "dataset_rows": int(len(df)),
        "positive_rate": round(float(y.mean()), 6),
        "test_rows": int(len(y_test)),
        "decision_threshold": DECISION_THRESHOLD,
        "candidate_metrics": results,
        "selected_model": selected_name,
        "selected_metrics": results[selected_name],
    }
    metrics_path.write_text(json.dumps(metrics_payload, indent=2), encoding="utf-8")

    metadata = {
        "project": "ClaimGuard AI",
        "model_name": selected_name,
        "model_version": "0.1.0",
        "trained_at": trained_at,
        "model_path": str(model_path),
        "data_path": str(data_path),
        "features": MODEL_FEATURES,
        "target": TARGET_COLUMN,
        "threshold": DECISION_THRESHOLD,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metrics_payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train and evaluate ClaimGuard models.")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA_PATH)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METRICS_PATH)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    metrics = train(args.data, args.model, args.metrics, args.metadata)
    selected = metrics["selected_model"]
    selected_metrics = metrics["selected_metrics"]
    print(f"Selected model: {selected}")
    print(json.dumps(selected_metrics, indent=2))


if __name__ == "__main__":
    main()
