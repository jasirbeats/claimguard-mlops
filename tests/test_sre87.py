from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from claimguard.sre87.config import SRE87Config
from claimguard.sre87.exit_codes import ExitCode
from claimguard.sre87.models import ClaimRecord
from claimguard.sre87.orchestrator import SRE87ControlCycle
from claimguard.sre87.repository import JsonClaimRepository
from claimguard.sre87.routing import route_for_status
from claimguard.sre87.seed import seed_demo_repository

NOW = datetime(2026, 8, 5, 19, 0, tzinfo=timezone(timedelta(hours=-5)))


def make_config(tmp_path: Path, *, include_status_660: bool = False) -> SRE87Config:
    return SRE87Config.from_dict(
        {
            "environment": "TEST",
            "thresholds": {
                "claim_age_hours": 2,
                "success_status": 300,
                "eligible_statuses": [655, 665, 800, 850],
                "include_status_660": include_status_660,
            },
            "paths": {
                "claims_file": str(tmp_path / "claims.json"),
                "runtime_root": str(tmp_path / "runtime"),
            },
            "incident": {
                "enabled": True,
                "assignment_group": "TEST_SUPPORT",
            },
        }
    )


def test_routing_contract() -> None:
    assert route_for_status(655).request_mode == "bulk-json"
    assert route_for_status(665).assigned_layer == "CDR Persistence"
    assert route_for_status(660).assigned_layer == "CDR Persistence"
    assert route_for_status(800).request_mode == "single-query"
    assert route_for_status(850).request_mode == "single-json"


def test_eligibility_excludes_young_success_and_660_by_default(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    repository = JsonClaimRepository(config.paths.claims_file)
    repository.write_claims(
        [
            ClaimRecord("old-655", 655, NOW - timedelta(hours=3)),
            ClaimRecord("young-655", 655, NOW - timedelta(minutes=30)),
            ClaimRecord("old-300", 300, NOW - timedelta(hours=4)),
            ClaimRecord("old-660", 660, NOW - timedelta(hours=4)),
        ]
    )
    eligible = repository.eligible_claims(
        now=NOW,
        age_hours=config.thresholds.claim_age_hours,
        statuses=config.thresholds.effective_eligible_statuses,
    )
    assert [claim.claim_tracking_id for claim in eligible] == ["old-655"]


def test_happy_cycle_routes_bulk_and_individual_calls(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    seed_demo_repository(JsonClaimRepository(config.paths.claims_file), now=NOW)
    cycle = SRE87ControlCycle(config)

    code, summary = cycle.run(now=NOW)

    assert code == ExitCode.SUCCESS
    assert summary.status == "SUCCESS"
    assert len(summary.recovery_results) == 4
    request_ids_655_665 = {
        result.request_id
        for result in summary.recovery_results
        if result.source_status in {655, 665}
    }
    assert len(request_ids_655_665) == 2  # one bulk call per status group
    assert all(result.post_recovery_status == 300 for result in summary.recovery_results)
    assert cycle.recovery.request_count == 4  # 655 bulk, 665 bulk, 800 single, 850 single
    assert Path(summary.output_json or "").exists()
    assert Path(summary.output_csv or "").exists()
    assert Path(summary.output_log or "").exists()


def test_dry_run_never_executes_endpoint_or_submits_state(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    repository = JsonClaimRepository(config.paths.claims_file)
    seed_demo_repository(repository, now=NOW)
    cycle = SRE87ControlCycle(config)

    code, summary = cycle.run(dry_run=True, now=NOW)

    assert code == ExitCode.SUCCESS
    assert summary.status == "DRY_RUN"
    assert cycle.recovery.request_count == 0
    assert repository.get_statuses(["SRE87-655-001"])["SRE87-655-001"] == 655
    state = json.loads(config.paths.state_file.read_text())
    assert state["submitted_ids"] == []


def test_unresolved_prior_run_halts_before_new_query_and_creates_one_incident(
    tmp_path: Path,
) -> None:
    config = make_config(tmp_path)
    repository = JsonClaimRepository(config.paths.claims_file)
    seed_demo_repository(repository, scenario="unresolved", now=NOW)
    first_cycle = SRE87ControlCycle(config)

    first_code, first_summary = first_cycle.run(now=NOW)
    second_cycle = SRE87ControlCycle(config)
    second_code, second_summary = second_cycle.run(now=NOW + timedelta(hours=1))

    assert first_code == ExitCode.SUCCESS
    assert any(
        result.claim_tracking_id == "SRE87-665-001" and result.post_recovery_status == 665
        for result in first_summary.recovery_results
    )
    assert second_code == ExitCode.PRIOR_RUN_HALT
    assert second_summary.status == "HALTED_PRIOR_RUN"
    assert second_summary.eligible_claim_count == 0
    assert second_cycle.recovery.request_count == 0
    incidents = config.paths.incidents_file.read_text().strip().splitlines()
    assert len(incidents) == 1


def test_endpoint_failure_exits_two_without_retry(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    seed_demo_repository(
        JsonClaimRepository(config.paths.claims_file),
        scenario="endpoint-failure",
        now=NOW,
    )
    cycle = SRE87ControlCycle(config)

    code, summary = cycle.run(now=NOW)

    assert code == ExitCode.RUNTIME_FAILURE
    assert summary.status == "RUNTIME_FAILURE"
    assert cycle.recovery.request_count == 4
    assert all(result.response_code == 503 for result in summary.recovery_results)
    assert summary.incident is not None


def test_pause_and_resume_control(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    seed_demo_repository(JsonClaimRepository(config.paths.claims_file), now=NOW)
    cycle = SRE87ControlCycle(config)
    cycle.state.pause()

    code, summary = cycle.run(now=NOW)

    assert code == ExitCode.SUCCESS
    assert summary.status == "PAUSED"
    assert cycle.recovery.request_count == 0
    cycle.state.resume()
    assert cycle.state.is_paused() is False
