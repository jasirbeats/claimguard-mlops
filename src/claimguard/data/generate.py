from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from claimguard.config import DEFAULT_DATA_PATH


def generate_claims(rows: int = 10_000, seed: int = 42) -> pd.DataFrame:
    """Generate a reproducible synthetic claims-processing dataset."""
    if rows < 100:
        raise ValueError("rows must be at least 100")

    rng = np.random.default_rng(seed)

    claim_type = rng.choice(
        ["professional", "institutional", "dental", "pharmacy"],
        size=rows,
        p=[0.45, 0.30, 0.15, 0.10],
    )
    state_code = rng.choice(
        ["LA", "TX", "FL", "GA", "MS", "AL", "AZ", "IN"], size=rows
    )
    provider_type = rng.choice(
        ["hospital", "clinic", "specialist", "pharmacy", "laboratory"],
        size=rows,
        p=[0.25, 0.30, 0.20, 0.15, 0.10],
    )
    source_system = rng.choice(
        ["portal", "edi", "batch", "api"], size=rows, p=[0.15, 0.45, 0.25, 0.15]
    )

    claim_amount = np.round(rng.lognormal(mean=7.2, sigma=1.0, size=rows), 2)
    retry_count = np.clip(rng.poisson(lam=0.65, size=rows), 0, 6)
    queue_depth = np.clip(rng.gamma(shape=2.2, scale=45, size=rows).astype(int), 0, 500)
    processing_duration_seconds = np.clip(
        rng.lognormal(mean=7.5, sigma=0.8, size=rows).astype(int), 30, 86_400
    )
    previous_failure_count = np.clip(rng.poisson(lam=0.35, size=rows), 0, 5)
    hour_of_day = rng.integers(0, 24, size=rows)
    day_of_week = rng.integers(0, 7, size=rows)
    procedure_count = np.clip(rng.poisson(lam=3.0, size=rows) + 1, 1, 20)

    endpoint_response_code = np.where(
        rng.random(rows) < 0.82,
        "200",
        rng.choice(["400", "408", "429", "500", "503"], size=rows),
    )

    # Hidden operational relationship used only to synthesize the target.
    risk_score = (
        -3.8
        + 0.55 * retry_count
        + 0.010 * queue_depth
        + 0.00012 * processing_duration_seconds
        + 0.70 * previous_failure_count
        + 0.00005 * np.maximum(claim_amount - 5_000, 0)
        + 0.60 * np.isin(endpoint_response_code, ["408", "429", "500", "503"])
        + 0.40 * (source_system == "batch")
        + 0.25 * (provider_type == "hospital")
        + 0.30 * np.isin(hour_of_day, [0, 1, 2, 3, 4, 5])
        + rng.normal(0, 0.55, size=rows)
    )
    probability = 1 / (1 + np.exp(-risk_score))
    will_become_stuck = rng.binomial(1, probability)

    received_at = pd.Timestamp("2026-01-01", tz="UTC") + pd.to_timedelta(
        rng.integers(0, 180 * 24 * 60, size=rows), unit="m"
    )

    return pd.DataFrame(
        {
            "claim_tracking_id": [f"SYN-{seed}-{i:08d}" for i in range(rows)],
            "received_at": received_at.astype(str),
            "claim_type": claim_type,
            "state_code": state_code,
            "provider_type": provider_type,
            "source_system": source_system,
            "claim_amount": claim_amount,
            "retry_count": retry_count,
            "queue_depth": queue_depth,
            "processing_duration_seconds": processing_duration_seconds,
            "previous_failure_count": previous_failure_count,
            "hour_of_day": hour_of_day,
            "day_of_week": day_of_week,
            "procedure_count": procedure_count,
            "endpoint_response_code": endpoint_response_code,
            "will_become_stuck": will_become_stuck,
        }
    )


def write_dataset(output: Path, rows: int, seed: int) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    df = generate_claims(rows=rows, seed=seed)
    df.to_csv(output, index=False)
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate synthetic ClaimGuard training data.")
    parser.add_argument("--rows", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=DEFAULT_DATA_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = write_dataset(args.output, args.rows, args.seed)
    print(f"Generated {args.rows:,} records at {output}")


if __name__ == "__main__":
    main()
