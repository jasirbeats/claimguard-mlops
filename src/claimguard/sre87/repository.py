from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from claimguard.sre87.models import ClaimRecord


class JsonClaimRepository:
    """Synthetic, file-backed substitute for the enterprise Oracle claim table."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def list_claims(self) -> list[ClaimRecord]:
        if not self.path.exists():
            return []
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        claims = [ClaimRecord.from_dict(value) for value in payload]
        ids = [claim.claim_tracking_id for claim in claims]
        if len(ids) != len(set(ids)):
            raise ValueError("Claim repository contains duplicate claim_tracking_id values")
        return claims

    def write_claims(self, claims: list[ClaimRecord]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [claim.to_dict() for claim in claims]
        _atomic_json_write(self.path, payload)

    def get_statuses(self, claim_ids: list[str]) -> dict[str, int]:
        wanted = set(claim_ids)
        return {
            claim.claim_tracking_id: claim.process_status
            for claim in self.list_claims()
            if claim.claim_tracking_id in wanted
        }

    def get_claims(self, claim_ids: list[str]) -> list[ClaimRecord]:
        wanted = set(claim_ids)
        return [claim for claim in self.list_claims() if claim.claim_tracking_id in wanted]

    def eligible_claims(
        self,
        *,
        now: datetime,
        age_hours: float,
        statuses: tuple[int, ...],
    ) -> list[ClaimRecord]:
        threshold = now - timedelta(hours=age_hours)
        return sorted(
            [
                claim
                for claim in self.list_claims()
                if claim.process_status in statuses and claim.claim_receipt_time < threshold
            ],
            key=lambda claim: (
                claim.process_status,
                claim.claim_receipt_time,
                claim.claim_tracking_id,
            ),
        )

    def update_status(self, claim_ids: list[str], status: int) -> None:
        wanted = set(claim_ids)
        updated: list[ClaimRecord] = []
        for claim in self.list_claims():
            if claim.claim_tracking_id in wanted:
                updated.append(
                    ClaimRecord(
                        claim_tracking_id=claim.claim_tracking_id,
                        process_status=status,
                        claim_receipt_time=claim.claim_receipt_time,
                        mock_recovery_outcome=claim.mock_recovery_outcome,
                    )
                )
            else:
                updated.append(claim)
        self.write_claims(updated)


def _atomic_json_write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2)
            stream.write("\n")
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise
