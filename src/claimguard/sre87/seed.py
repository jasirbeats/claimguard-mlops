from __future__ import annotations

from dataclasses import replace
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
        _claim(
            "SRE87-655-001",
            655,
            current - timedelta(hours=4),
            claim_amount=2_850,
            retry_count=2,
            queue_depth=310,
            endpoint_latency_ms=780,
            previous_failure_count=1,
            source_system="EDI",
            provider_type="PROFESSIONAL",
        ),
        _claim(
            "SRE87-665-001",
            665,
            current - timedelta(hours=3),
            claim_amount=8_900,
            retry_count=3,
            queue_depth=520,
            endpoint_latency_ms=1_280,
            previous_failure_count=2,
            source_system="BATCH",
            provider_type="FACILITY",
        ),
        _claim(
            "SRE87-800-001",
            800,
            current - timedelta(hours=5),
            claim_amount=4_200,
            retry_count=1,
            queue_depth=275,
            endpoint_latency_ms=880,
            previous_failure_count=1,
            source_system="EDI",
            provider_type="FACILITY",
        ),
        _claim(
            "SRE87-850-001",
            850,
            current - timedelta(hours=2, minutes=30),
            claim_amount=12_500,
            retry_count=4,
            queue_depth=610,
            endpoint_latency_ms=1_620,
            previous_failure_count=3,
            source_system="BATCH",
            provider_type="PROFESSIONAL",
        ),
        _claim(
            "SRE87-YOUNG-655",
            655,
            current - timedelta(minutes=55),
            claim_amount=850,
            retry_count=0,
            queue_depth=95,
            endpoint_latency_ms=260,
            previous_failure_count=0,
            source_system="API",
            provider_type="PROFESSIONAL",
        ),
        _claim(
            "SRE87-COMPLETE-300",
            300,
            current - timedelta(hours=8),
            claim_amount=1_100,
            retry_count=0,
            queue_depth=40,
            endpoint_latency_ms=120,
            previous_failure_count=0,
            source_system="PORTAL",
            provider_type="PHARMACY",
        ),
    ]
    if scenario == "unresolved":
        claims[1] = replace(claims[1], mock_recovery_outcome="remain")
    elif scenario == "endpoint-failure":
        claims = [
            replace(
                claim,
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
    *,
    claim_amount: float,
    retry_count: int,
    queue_depth: int,
    endpoint_latency_ms: float,
    previous_failure_count: int,
    source_system: str,
    provider_type: str,
) -> ClaimRecord:
    return ClaimRecord(
        claim_tracking_id=claim_tracking_id,
        process_status=process_status,
        claim_receipt_time=receipt_time,
        claim_amount=claim_amount,
        retry_count=retry_count,
        queue_depth=queue_depth,
        endpoint_latency_ms=endpoint_latency_ms,
        previous_failure_count=previous_failure_count,
        source_system=source_system,
        provider_type=provider_type,
    )
