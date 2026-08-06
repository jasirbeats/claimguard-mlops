from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime

from claimguard.sre87.ai.scoring import SRE87RiskScorer
from claimguard.sre87.config import SRE87Config
from claimguard.sre87.exit_codes import ExitCode
from claimguard.sre87.incidents import MockIncidentService
from claimguard.sre87.models import ClaimRecord, PriorValidation, RiskAssessment, RunSummary
from claimguard.sre87.outputs import RunOutputWriter
from claimguard.sre87.recovery import MockRecoveryClient
from claimguard.sre87.repository import JsonClaimRepository
from claimguard.sre87.state import RunStateStore


class SRE87ControlCycle:
    def __init__(self, config: SRE87Config) -> None:
        self.config = config
        self.repository = JsonClaimRepository(config.paths.claims_file)
        self.state = RunStateStore(config.paths.state_file, config.paths.pause_file)
        self.recovery = MockRecoveryClient(
            self.repository,
            success_status=config.thresholds.success_status,
        )
        self.incidents = MockIncidentService(
            config.paths.incidents_file,
            assignment_group=config.incident.assignment_group,
            enabled=config.incident.enabled,
        )
        self.outputs = RunOutputWriter(config.paths.logs_root)
        self.risk_scorer = (
            SRE87RiskScorer(config.ai.model_path, config.ai.metadata_path)
            if config.ai.enabled
            else None
        )

    def run(
        self,
        *,
        dry_run: bool = False,
        now: datetime | None = None,
    ) -> tuple[ExitCode, RunSummary]:
        current = now or datetime.now(UTC)
        if current.tzinfo is None:
            raise ValueError("now must include a timezone")
        run_id = current.strftime("%Y%m%d_%H%M%S")
        started_at = current.isoformat()
        events = [self._event(current, f"SRE 87 run {run_id} started")]
        empty_validation = PriorValidation(checked_count=0, unresolved_ids=[], missing_ids=[])

        try:
            if self.state.is_paused():
                events.append(self._event(current, "Control cycle skipped: automation is paused"))
                summary = self._summary(
                    run_id=run_id,
                    started_at=started_at,
                    completed_at=current.isoformat(),
                    status="PAUSED",
                    exit_code=ExitCode.SUCCESS,
                    dry_run=dry_run,
                    paused=True,
                    prior_validation=empty_validation,
                )
                return ExitCode.SUCCESS, self.outputs.write(summary, events, current)

            prior = self._validate_prior_run()
            events.append(
                self._event(
                    current,
                    "Prior-run validation: "
                    f"checked={prior.checked_count} unresolved={len(prior.unresolved_ids)} "
                    f"missing={len(prior.missing_ids)}",
                )
            )
            if prior.halt_required:
                unresolved = sorted(set(prior.unresolved_ids + prior.missing_ids))
                incident = self.incidents.create(
                    run_id=run_id,
                    incident_type="PRIOR_RUN_UNRESOLVED",
                    summary=(
                        f"SRE 87 halted: {len(unresolved)} prior-cycle claims "
                        "did not reach status 300."
                    ),
                    unresolved_ids=unresolved,
                    created_at=current,
                )
                events.append(self._event(current, "HALT: no new stuck-claim query was executed"))
                summary = self._summary(
                    run_id=run_id,
                    started_at=started_at,
                    completed_at=current.isoformat(),
                    status="HALTED_PRIOR_RUN",
                    exit_code=ExitCode.PRIOR_RUN_HALT,
                    dry_run=dry_run,
                    paused=False,
                    prior_validation=prior,
                    incident=incident,
                )
                return ExitCode.PRIOR_RUN_HALT, self.outputs.write(summary, events, current)

            eligible = self.repository.eligible_claims(
                now=current,
                age_hours=self.config.thresholds.claim_age_hours,
                statuses=self.config.thresholds.effective_eligible_statuses,
            )
            counts = Counter(str(claim.process_status) for claim in eligible)
            events.append(
                self._event(
                    current,
                    f"Eligible claims older than {self.config.thresholds.claim_age_hours:g}h: "
                    f"{len(eligible)}",
                )
            )

            risk_assessments, ai_scoring_status = self._score_claims(eligible, now=current)
            if ai_scoring_status == "scored":
                for assessment in sorted(
                    risk_assessments, key=lambda value: value.priority_score, reverse=True
                ):
                    events.append(
                        self._event(
                            current,
                            "AI advisory "
                            f"id={assessment.claim_tracking_id} "
                            f"risk={assessment.risk_level} "
                            f"probability={assessment.probability:.3f} "
                            f"priority={assessment.priority_score}",
                        )
                    )
            elif ai_scoring_status == "unavailable":
                events.append(
                    self._event(
                        current,
                        "AI advisory unavailable; deterministic SRE 87 routing remains active",
                    )
                )

            if not eligible:
                self.state.save(
                    run_id=run_id,
                    completed_at=current.isoformat(),
                    submitted_ids=[],
                )
                summary = self._summary(
                    run_id=run_id,
                    started_at=started_at,
                    completed_at=current.isoformat(),
                    status="NO_STUCK_CLAIMS",
                    exit_code=ExitCode.SUCCESS,
                    dry_run=dry_run,
                    paused=False,
                    prior_validation=prior,
                    eligible_claim_count=0,
                    eligible_claims_by_status=dict(counts),
                    risk_assessments=risk_assessments,
                    ai_scoring_status=ai_scoring_status,
                )
                return ExitCode.SUCCESS, self.outputs.write(summary, events, current)

            results = self.recovery.reprocess(eligible, dry_run=dry_run, executed_at=current)
            for result in results:
                events.append(
                    self._event(
                        current,
                        f"route status={result.source_status} id={result.claim_tracking_id} "
                        f"layer={result.assigned_layer} mode={result.request_mode} "
                        f"response={result.response_code}",
                    )
                )

            submitted_ids = [] if dry_run else [claim.claim_tracking_id for claim in eligible]
            self.state.save(
                run_id=run_id,
                completed_at=current.isoformat(),
                submitted_ids=submitted_ids,
            )

            failed_results = [result for result in results if not result.accepted]
            if failed_results:
                failed_ids = [result.claim_tracking_id for result in failed_results]
                incident = self.incidents.create(
                    run_id=run_id,
                    incident_type="RECOVERY_RUNTIME_FAILURE",
                    summary=(
                        f"SRE 87 recovery failed for {len(failed_ids)} claim action(s); "
                        "no same-cycle retries were attempted."
                    ),
                    unresolved_ids=failed_ids,
                    created_at=current,
                )
                status = "RUNTIME_FAILURE"
                code = ExitCode.RUNTIME_FAILURE
            else:
                incident = None
                status = "DRY_RUN" if dry_run else "SUCCESS"
                code = ExitCode.SUCCESS

            summary = self._summary(
                run_id=run_id,
                started_at=started_at,
                completed_at=current.isoformat(),
                status=status,
                exit_code=code,
                dry_run=dry_run,
                paused=False,
                prior_validation=prior,
                eligible_claim_count=len(eligible),
                eligible_claims_by_status=dict(counts),
                recovery_results=results,
                risk_assessments=risk_assessments,
                ai_scoring_status=ai_scoring_status,
                incident=incident,
            )
            return code, self.outputs.write(summary, events, current)
        except Exception as exc:
            events.append(self._event(current, f"UNEXPECTED FAILURE: {exc}"))
            summary = self._summary(
                run_id=run_id,
                started_at=started_at,
                completed_at=current.isoformat(),
                status="UNEXPECTED_FAILURE",
                exit_code=ExitCode.UNEXPECTED_FAILURE,
                dry_run=dry_run,
                paused=self.state.is_paused(),
                prior_validation=empty_validation,
            )
            return ExitCode.UNEXPECTED_FAILURE, self.outputs.write(summary, events, current)

    def _validate_prior_run(self) -> PriorValidation:
        state = self.state.load()
        submitted = [str(value) for value in state.get("submitted_ids", [])]
        if not submitted:
            return PriorValidation(checked_count=0, unresolved_ids=[], missing_ids=[])
        statuses = self.repository.get_statuses(submitted)
        missing = [claim_id for claim_id in submitted if claim_id not in statuses]
        unresolved = [
            claim_id
            for claim_id in submitted
            if statuses.get(claim_id) != self.config.thresholds.success_status
        ]
        unresolved = [claim_id for claim_id in unresolved if claim_id not in missing]
        return PriorValidation(
            checked_count=len(statuses),
            unresolved_ids=unresolved,
            missing_ids=missing,
        )

    def _summary(
        self,
        *,
        run_id: str,
        started_at: str,
        completed_at: str,
        status: str,
        exit_code: ExitCode,
        dry_run: bool,
        paused: bool,
        prior_validation: PriorValidation,
        eligible_claim_count: int = 0,
        eligible_claims_by_status: dict[str, int] | None = None,
        recovery_results: list | None = None,
        risk_assessments: list[RiskAssessment] | None = None,
        ai_scoring_status: str = "disabled",
        incident=None,
    ) -> RunSummary:
        return RunSummary(
            run_id=run_id,
            started_at=started_at,
            completed_at=completed_at,
            environment=self.config.environment,
            status=status,
            exit_code=int(exit_code),
            dry_run=dry_run,
            paused=paused,
            eligible_claim_count=eligible_claim_count,
            eligible_claims_by_status=eligible_claims_by_status or {},
            prior_validation=prior_validation,
            recovery_results=recovery_results or [],
            risk_assessments=risk_assessments or [],
            ai_scoring_status=ai_scoring_status,
            incident=incident,
        )

    def _score_claims(
        self,
        claims: list[ClaimRecord],
        *,
        now: datetime,
    ) -> tuple[list[RiskAssessment], str]:
        if not self.config.ai.enabled:
            return [], "disabled"
        if self.risk_scorer is None or not self.risk_scorer.available:
            return [], "unavailable"
        return self.risk_scorer.score(claims, now=now), "scored"

    @staticmethod
    def _event(timestamp: datetime, message: str) -> str:
        return f"{timestamp.isoformat()} {message}"
