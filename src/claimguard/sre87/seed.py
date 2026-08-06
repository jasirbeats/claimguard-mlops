from __future__ import annotations

from datetime import UTC, datetime, timedelta

from claimguard.sre87.models import ClaimRecord
from claimguard.sre87.repository import JsonClaimRepository

SCENARIOS = ("happy", "unresolved", "endpoint-failure")


def seed_demo_repository(
    repository: JsonClaimRepository,
    *,
    scenario: str = "happy",
    now: datetime | None = None,
) -> list[ClaimRecord]:
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown scenario {scenario!r}; choose from {SCENARIOS}")
    current = now or datetime.now(UTC)
    claims = [
        _claim("SRE87-655-001", 655, current - timedelta(hours=4), "resolve"),
        _claim("SRE87-665-001", 665, current - timedelta(hours=3), "resolve"),
        _claim("SRE87-800-001", 800, current - timedelta(hours=5), "resolve"),
        _claim("SRE87-850-001", 850, current - timedelta(hours=2, minutes=30), "resolve"),
        _claim("SRE87-YOUNG-655", 655, current - timedelta(minutes=55), "resolve"),
        _claim("SRE87-COMPLETE-300", 300, current - timedelta(hours=8), "resolve"),
    ]
    if scenario == "unresolved":
        claims[1] = _claim("SRE87-665-001", 665, current - timedelta(hours=3), "remain")
    elif scenario == "endpoint-failure":
        claims = [
            ClaimRecord(
                claim_tracking_id=claim.claim_tracking_id,
                process_status=claim.process_status,
                claim_receipt_time=claim.claim_receipt_time,
                mock_recovery_outcome=(
                    "fail"
                    if claim.process_status in {655, 665, 800, 850}
                    else claim.mock_recovery_outcome
                ),
            )
            for claim in claims
        ]
    repository.write_claims(claims)
    return claims


def _claim(
    claim_tracking_id: str,
    process_status: int,
    receipt_time: datetime,
    outcome: str,
) -> ClaimRecord:
    return ClaimRecord(
        claim_tracking_id=claim_tracking_id,
        process_status=process_status,
        claim_receipt_time=receipt_time,
        mock_recovery_outcome=outcome,
    )
