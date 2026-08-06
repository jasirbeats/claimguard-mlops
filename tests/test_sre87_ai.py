from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from claimguard.sre87.ai.features import claims_to_frame
from claimguard.sre87.ai.scoring import SRE87RiskScorer
from claimguard.sre87.ai.training import generate_training_frame, train_risk_model
from claimguard.sre87.config import SRE87Config
from claimguard.sre87.exit_codes import ExitCode
from claimguard.sre87.models import ClaimRecord
from claimguard.sre87.orchestrator import SRE87ControlCycle
from claimguard.sre87.repository import JsonClaimRepository
from claimguard.sre87.seed import seed_demo_repository

NOW = datetime(2026, 8, 5, 19, 0, tzinfo=timezone(timedelta(hours=-5)))


def ai_config(tmp_path: Path, *, model_exists: bool = True) -> SRE87Config:
    model_path = tmp_path / "sre87-risk.joblib"
    metadata_path = tmp_path / "sre87-risk-metadata.json"
    if model_exists:
        train_risk_model(
            rows=800,
            seed=87,
            model_path=model_path,
            metadata_path=metadata_path,
            metrics_path=tmp_path / "sre87-risk-metrics.json",
            enable_mlflow=False,
            candidate_names=("logistic_regression",),
        )
    return SRE87Config.from_dict(
        {
            "environment": "TEST",
            "thresholds": {
                "claim_age_hours": 2,
                "success_status": 300,
                "eligible_statuses": [655, 665, 800, 850],
                "include_status_660": False,
            },
            "paths": {
                "claims_file": str(tmp_path / "claims.json"),
                "runtime_root": str(tmp_path / "runtime"),
            },
            "incident": {
                "enabled": True,
                "assignment_group": "TEST_SUPPORT",
            },
            "ai": {
                "enabled": True,
                "model_path": str(model_path),
                "metadata_path": str(metadata_path),
            },
        }
    )


def test_synthetic_risk_training_data_has_signal() -> None:
    frame = generate_training_frame(rows=1_000, seed=87)
    assert len(frame) == 1_000
    assert 0.05 < frame["will_remain_non_300"].mean() < 0.85
    high_retry = frame.loc[frame["retry_count"] >= 3, "will_remain_non_300"].mean()
    no_retry = frame.loc[frame["retry_count"] == 0, "will_remain_non_300"].mean()
    assert high_retry > no_retry


def test_claim_features_include_operational_telemetry() -> None:
    claim = ClaimRecord(
        "claim-1",
        665,
        NOW - timedelta(hours=3),
        claim_amount=7_500,
        retry_count=2,
        queue_depth=420,
        endpoint_latency_ms=1_100,
        previous_failure_count=1,
        source_system="EDI",
        provider_type="FACILITY",
    )
    frame = claims_to_frame([claim], now=NOW)
    assert frame.iloc[0]["age_hours"] == 3.0
    assert frame.iloc[0]["queue_depth"] == 420.0
    assert frame.iloc[0]["source_system"] == "EDI"


def test_training_creates_loadable_advisory_model(tmp_path: Path) -> None:
    model_path = tmp_path / "model.joblib"
    metadata_path = tmp_path / "metadata.json"
    result = train_risk_model(
        rows=800,
        seed=87,
        model_path=model_path,
        metadata_path=metadata_path,
        metrics_path=tmp_path / "metrics.json",
        enable_mlflow=False,
        candidate_names=("logistic_regression",),
    )
    scorer = SRE87RiskScorer(model_path, metadata_path)
    assert result.selected_model == "logistic_regression"
    assert result.metrics["recall"] > 0
    assert scorer.available is True
    assert scorer.metadata["advisory_only"] is True


def test_ai_scoring_is_added_without_overriding_routes(tmp_path: Path) -> None:
    config = ai_config(tmp_path)
    seed_demo_repository(JsonClaimRepository(config.paths.claims_file), now=NOW)
    cycle = SRE87ControlCycle(config)

    code, summary = cycle.run(now=NOW)

    assert code == ExitCode.SUCCESS
    assert summary.ai_scoring_status == "scored"
    assert len(summary.risk_assessments) == 4
    route_by_id = {
        result.claim_tracking_id: result.assigned_layer for result in summary.recovery_results
    }
    for assessment in summary.risk_assessments:
        assert assessment.advisory_only is True
        assert assessment.routing_authority == "deterministic_sre87_rules"
        assert assessment.likely_failure_layer == route_by_id[assessment.claim_tracking_id]
        assert 0 <= assessment.priority_score <= 100


def test_missing_ai_model_fails_open_and_preserves_recovery(tmp_path: Path) -> None:
    config = ai_config(tmp_path, model_exists=False)
    seed_demo_repository(JsonClaimRepository(config.paths.claims_file), now=NOW)
    cycle = SRE87ControlCycle(config)

    code, summary = cycle.run(now=NOW)

    assert code == ExitCode.SUCCESS
    assert summary.status == "SUCCESS"
    assert summary.ai_scoring_status == "unavailable"
    assert summary.risk_assessments == []
    assert len(summary.recovery_results) == 4


def test_status_updates_preserve_ai_features(tmp_path: Path) -> None:
    repository = JsonClaimRepository(tmp_path / "claims.json")
    claim = ClaimRecord(
        "claim-1",
        665,
        NOW - timedelta(hours=3),
        claim_amount=9_100,
        retry_count=3,
        queue_depth=510,
        endpoint_latency_ms=1_250,
        previous_failure_count=2,
        source_system="BATCH",
        provider_type="FACILITY",
    )
    repository.write_claims([claim])
    repository.update_status(["claim-1"], 300)
    updated = repository.list_claims()[0]
    assert updated.process_status == 300
    assert updated.claim_amount == 9_100
    assert updated.queue_depth == 510
    assert updated.source_system == "BATCH"
