from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from uuid import uuid4

from claimguard.sre87.models import ClaimRecord, RecoveryResult
from claimguard.sre87.repository import JsonClaimRepository
from claimguard.sre87.routing import route_for_status


class MockRecoveryClient:
    """Safe endpoint simulator. It never calls employer or external systems."""

    def __init__(self, repository: JsonClaimRepository, success_status: int) -> None:
        self.repository = repository
        self.success_status = success_status
        self.request_count = 0

    def reprocess(
        self,
        claims: list[ClaimRecord],
        *,
        dry_run: bool,
        executed_at: datetime,
    ) -> list[RecoveryResult]:
        grouped: dict[int, list[ClaimRecord]] = defaultdict(list)
        for claim in claims:
            grouped[claim.process_status].append(claim)

        results: list[RecoveryResult] = []
        for status in sorted(grouped):
            route = route_for_status(status)
            status_claims = grouped[status]
            if route.request_mode == "bulk-json":
                results.extend(
                    self._execute_group(status_claims, dry_run=dry_run, executed_at=executed_at)
                )
            else:
                for claim in status_claims:
                    results.extend(
                        self._execute_group([claim], dry_run=dry_run, executed_at=executed_at)
                    )
        return results

    def _execute_group(
        self,
        claims: list[ClaimRecord],
        *,
        dry_run: bool,
        executed_at: datetime,
    ) -> list[RecoveryResult]:
        route = route_for_status(claims[0].process_status)
        request_id = f"mock-{uuid4().hex[:12]}"
        if not dry_run:
            self.request_count += 1

        has_endpoint_failure = any(
            claim.mock_recovery_outcome == "fail" for claim in claims
        )
        accepted = dry_run or not has_endpoint_failure
        response_code = 0 if dry_run else (200 if accepted else 503)

        if accepted and not dry_run:
            resolvable = [
                claim.claim_tracking_id
                for claim in claims
                if claim.mock_recovery_outcome == "resolve"
            ]
            if resolvable:
                self.repository.update_status(resolvable, self.success_status)

        statuses_after = self.repository.get_statuses(
            [claim.claim_tracking_id for claim in claims]
        )
        return [
            RecoveryResult(
                claim_tracking_id=claim.claim_tracking_id,
                source_status=claim.process_status,
                assigned_layer=route.assigned_layer,
                endpoint_name=route.endpoint_name,
                request_mode=route.request_mode,
                request_id=request_id,
                response_code=response_code,
                accepted=accepted,
                dry_run=dry_run,
                execution_timestamp=executed_at.isoformat(),
                post_recovery_status=statuses_after.get(claim.claim_tracking_id),
            )
            for claim in claims
        ]
