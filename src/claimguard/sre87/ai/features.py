from __future__ import annotations

from datetime import datetime

import pandas as pd

from claimguard.sre87.models import ClaimRecord

NUMERIC_FEATURES = [
    "process_status",
    "age_hours",
    "claim_amount",
    "retry_count",
    "queue_depth",
    "endpoint_latency_ms",
    "previous_failure_count",
]
CATEGORICAL_FEATURES = ["source_system", "provider_type"]
FEATURE_COLUMNS = NUMERIC_FEATURES + CATEGORICAL_FEATURES


def claim_feature_row(claim: ClaimRecord, *, now: datetime) -> dict[str, object]:
    age_hours = max(0.0, (now - claim.claim_receipt_time).total_seconds() / 3600)
    return {
        "process_status": float(claim.process_status),
        "age_hours": float(age_hours),
        "claim_amount": float(claim.claim_amount),
        "retry_count": float(claim.retry_count),
        "queue_depth": float(claim.queue_depth),
        "endpoint_latency_ms": float(claim.endpoint_latency_ms),
        "previous_failure_count": float(claim.previous_failure_count),
        "source_system": str(claim.source_system),
        "provider_type": str(claim.provider_type),
    }


def claims_to_frame(claims: list[ClaimRecord], *, now: datetime) -> pd.DataFrame:
    rows = [claim_feature_row(claim, now=now) for claim in claims]
    return pd.DataFrame(rows, columns=FEATURE_COLUMNS)
