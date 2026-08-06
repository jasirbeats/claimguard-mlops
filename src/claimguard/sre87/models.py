from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


def parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"Timestamp must include a timezone: {value}")
    return parsed


@dataclass(frozen=True)
class ClaimRecord:
    claim_tracking_id: str
    process_status: int
    claim_receipt_time: datetime
    mock_recovery_outcome: str = "resolve"
    claim_amount: float = 0.0
    retry_count: int = 0
    queue_depth: int = 0
    endpoint_latency_ms: float = 0.0
    previous_failure_count: int = 0
    source_system: str = "UNKNOWN"
    provider_type: str = "UNKNOWN"

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ClaimRecord:
        return cls(
            claim_tracking_id=str(value["claim_tracking_id"]),
            process_status=int(value["process_status"]),
            claim_receipt_time=parse_datetime(str(value["claim_receipt_time"])),
            mock_recovery_outcome=str(value.get("mock_recovery_outcome", "resolve")),
            claim_amount=float(value.get("claim_amount", 0.0)),
            retry_count=int(value.get("retry_count", 0)),
            queue_depth=int(value.get("queue_depth", 0)),
            endpoint_latency_ms=float(value.get("endpoint_latency_ms", 0.0)),
            previous_failure_count=int(value.get("previous_failure_count", 0)),
            source_system=str(value.get("source_system", "UNKNOWN")),
            provider_type=str(value.get("provider_type", "UNKNOWN")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_tracking_id": self.claim_tracking_id,
            "process_status": self.process_status,
            "claim_receipt_time": self.claim_receipt_time.isoformat(),
            "mock_recovery_outcome": self.mock_recovery_outcome,
            "claim_amount": self.claim_amount,
            "retry_count": self.retry_count,
            "queue_depth": self.queue_depth,
            "endpoint_latency_ms": self.endpoint_latency_ms,
            "previous_failure_count": self.previous_failure_count,
            "source_system": self.source_system,
            "provider_type": self.provider_type,
        }


@dataclass(frozen=True)
class PriorValidation:
    checked_count: int
    unresolved_ids: list[str]
    missing_ids: list[str]

    @property
    def halt_required(self) -> bool:
        return bool(self.unresolved_ids or self.missing_ids)

    def to_dict(self) -> dict[str, Any]:
        return {
            "checked_count": self.checked_count,
            "unresolved_ids": self.unresolved_ids,
            "missing_ids": self.missing_ids,
            "halt_required": self.halt_required,
        }


@dataclass(frozen=True)
class RecoveryResult:
    claim_tracking_id: str
    source_status: int
    assigned_layer: str
    endpoint_name: str
    request_mode: str
    request_id: str
    response_code: int
    accepted: bool
    dry_run: bool
    execution_timestamp: str
    post_recovery_status: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RiskAssessment:
    claim_tracking_id: str
    probability: float
    risk_level: str
    priority_score: int
    likely_failure_layer: str
    recommended_action: str
    explanation: str
    model_name: str
    model_version: str
    advisory_only: bool
    routing_authority: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IncidentRecord:
    incident_id: str
    run_id: str
    incident_type: str
    assignment_group: str
    summary: str
    unresolved_ids: list[str]
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RunSummary:
    run_id: str
    started_at: str
    completed_at: str
    environment: str
    status: str
    exit_code: int
    dry_run: bool
    paused: bool
    eligible_claim_count: int
    eligible_claims_by_status: dict[str, int]
    prior_validation: PriorValidation
    recovery_results: list[RecoveryResult] = field(default_factory=list)
    risk_assessments: list[RiskAssessment] = field(default_factory=list)
    ai_scoring_status: str = "disabled"
    incident: IncidentRecord | None = None
    output_json: str | None = None
    output_csv: str | None = None
    output_log: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "environment": self.environment,
            "status": self.status,
            "exit_code": self.exit_code,
            "dry_run": self.dry_run,
            "paused": self.paused,
            "eligible_claim_count": self.eligible_claim_count,
            "eligible_claims_by_status": self.eligible_claims_by_status,
            "prior_validation": self.prior_validation.to_dict(),
            "ai_scoring_status": self.ai_scoring_status,
            "risk_assessments": [assessment.to_dict() for assessment in self.risk_assessments],
            "recovery_results": [result.to_dict() for result in self.recovery_results],
            "incident": self.incident.to_dict() if self.incident else None,
            "outputs": {
                "json": self.output_json,
                "csv": self.output_csv,
                "log": self.output_log,
            },
        }
