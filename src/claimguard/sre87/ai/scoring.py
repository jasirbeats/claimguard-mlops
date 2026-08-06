from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import joblib

from claimguard.sre87.ai.features import claims_to_frame
from claimguard.sre87.models import ClaimRecord, RiskAssessment
from claimguard.sre87.routing import route_for_status


class SRE87RiskScorer:
    """Advisory model scorer. It never selects or changes recovery routes."""

    def __init__(self, model_path: Path, metadata_path: Path) -> None:
        self.model_path = model_path
        self.metadata_path = metadata_path
        self._pipeline: Any | None = None
        self._metadata: dict[str, Any] = {}
        self.load_error: str | None = None
        self._load()

    @property
    def available(self) -> bool:
        return self._pipeline is not None

    @property
    def metadata(self) -> dict[str, Any]:
        return dict(self._metadata)

    def _load(self) -> None:
        if not self.model_path.exists():
            self.load_error = f"Model artifact not found: {self.model_path}"
            return
        try:
            self._pipeline = joblib.load(self.model_path)
            if self.metadata_path.exists():
                self._metadata = json.loads(self.metadata_path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - defensive runtime path
            self._pipeline = None
            self.load_error = str(exc)

    def score(self, claims: list[ClaimRecord], *, now: datetime) -> list[RiskAssessment]:
        if not claims or not self.available:
            return []
        frame = claims_to_frame(claims, now=now)
        probabilities = self._pipeline.predict_proba(frame)[:, 1]
        return [
            self._assessment(claim, probability=float(probability), now=now)
            for claim, probability in zip(claims, probabilities, strict=True)
        ]

    def _assessment(
        self,
        claim: ClaimRecord,
        *,
        probability: float,
        now: datetime,
    ) -> RiskAssessment:
        age_hours = max(0.0, (now - claim.claim_receipt_time).total_seconds() / 3600)
        risk_level = _risk_level(probability)
        priority_score = min(
            100,
            round(
                probability * 70
                + min(age_hours / 8, 1) * 15
                + min(claim.previous_failure_count / 4, 1) * 8
                + min(claim.retry_count / 5, 1) * 7
            ),
        )
        route = route_for_status(claim.process_status)
        explanation = _explanation(claim, age_hours=age_hours, probability=probability)
        action = {
            "low": "Continue standard hourly monitoring.",
            "medium": "Review queue health and watch the next status transition.",
            "high": "Prioritize operational review while preserving the required SRE 87 route.",
            "critical": "Escalate for immediate review while preserving the required SRE 87 route.",
        }[risk_level]
        return RiskAssessment(
            claim_tracking_id=claim.claim_tracking_id,
            probability=round(probability, 6),
            risk_level=risk_level,
            priority_score=priority_score,
            likely_failure_layer=route.assigned_layer,
            recommended_action=action,
            explanation=explanation,
            model_name=str(self._metadata.get("model_name", "unknown")),
            model_version=str(self._metadata.get("model_version", "unknown")),
            advisory_only=True,
            routing_authority="deterministic_sre87_rules",
        )


def _risk_level(probability: float) -> str:
    if probability >= 0.80:
        return "critical"
    if probability >= 0.60:
        return "high"
    if probability >= 0.35:
        return "medium"
    return "low"


def _explanation(claim: ClaimRecord, *, age_hours: float, probability: float) -> str:
    drivers: list[str] = []
    if age_hours >= 4:
        drivers.append(f"claim age is {age_hours:.1f} hours")
    elif age_hours >= 2:
        drivers.append(f"claim crossed the two-hour threshold ({age_hours:.1f}h)")
    if claim.retry_count >= 2:
        drivers.append(f"retry count is {claim.retry_count}")
    if claim.queue_depth >= 300:
        drivers.append(f"queue depth is elevated at {claim.queue_depth}")
    if claim.endpoint_latency_ms >= 1_000:
        drivers.append(f"endpoint latency is {claim.endpoint_latency_ms:.0f} ms")
    if claim.previous_failure_count:
        drivers.append(f"previous failures total {claim.previous_failure_count}")
    if not drivers:
        drivers.append("current status and baseline operating conditions")
    joined = ", ".join(drivers[:3])
    return f"Predicted unresolved probability is {probability:.1%}; primary signals: {joined}."
