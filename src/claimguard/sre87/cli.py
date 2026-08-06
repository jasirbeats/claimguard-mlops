from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from claimguard.sre87.ai.scoring import SRE87RiskScorer
from claimguard.sre87.config import SRE87Config
from claimguard.sre87.orchestrator import SRE87ControlCycle
from claimguard.sre87.repository import JsonClaimRepository
from claimguard.sre87.seed import SCENARIOS, seed_demo_repository
from claimguard.sre87.state import RunStateStore

DEFAULT_CONFIG = Path("config/sre87.demo.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the safe SRE 87 claim-recovery digital twin.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Execute one independent control cycle")
    run_parser.add_argument("--dry-run", action="store_true")
    run_parser.add_argument(
        "--now",
        help="Optional timezone-aware ISO timestamp for deterministic demonstrations",
    )

    seed_parser = subparsers.add_parser("seed", help="Create synthetic SRE 87 claims")
    seed_parser.add_argument("--scenario", choices=SCENARIOS, default="happy")
    seed_parser.add_argument("--now", help="Optional timezone-aware ISO timestamp")

    subparsers.add_parser("pause", help="Pause future control cycles")
    subparsers.add_parser("resume", help="Resume future control cycles")
    subparsers.add_parser("status", help="Show pause and last-run state")
    subparsers.add_parser("risk-preview", help="Score eligible claims without recovery calls")
    subparsers.add_parser("risk-model-info", help="Show advisory risk model metadata")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = SRE87Config.load(args.config)
    state = RunStateStore(config.paths.state_file, config.paths.pause_file)

    if args.command == "seed":
        repository = JsonClaimRepository(config.paths.claims_file)
        claims = seed_demo_repository(
            repository,
            scenario=args.scenario,
            now=_optional_datetime(args.now),
        )
        state.state_file.unlink(missing_ok=True)
        config.paths.incidents_file.unlink(missing_ok=True)
        print(
            json.dumps(
                {
                    "scenario": args.scenario,
                    "claims_file": str(config.paths.claims_file),
                    "claims_created": len(claims),
                    "state_reset": True,
                },
                indent=2,
            )
        )
        return

    if args.command == "pause":
        state.pause()
        print(f"SRE 87 automation paused: {config.paths.pause_file}")
        return

    if args.command == "resume":
        state.resume()
        print("SRE 87 automation resumed")
        return

    if args.command == "status":
        print(
            json.dumps(
                {
                    "paused": state.is_paused(),
                    "state": state.load(),
                    "claims_file": str(config.paths.claims_file),
                    "incidents_file": str(config.paths.incidents_file),
                },
                indent=2,
            )
        )
        return

    if args.command == "risk-model-info":
        scorer = SRE87RiskScorer(config.ai.model_path, config.ai.metadata_path)
        print(
            json.dumps(
                {
                    "enabled": config.ai.enabled,
                    "available": scorer.available,
                    "load_error": scorer.load_error,
                    "model_path": str(config.ai.model_path),
                    "metadata_path": str(config.ai.metadata_path),
                    "metadata": scorer.metadata,
                },
                indent=2,
            )
        )
        return

    if args.command == "risk-preview":
        scorer = SRE87RiskScorer(config.ai.model_path, config.ai.metadata_path)
        current = datetime.now().astimezone()
        repository = JsonClaimRepository(config.paths.claims_file)
        eligible = repository.eligible_claims(
            now=current,
            age_hours=config.thresholds.claim_age_hours,
            statuses=config.thresholds.effective_eligible_statuses,
        )
        assessments = scorer.score(eligible, now=current)
        print(
            json.dumps(
                {
                    "available": scorer.available,
                    "load_error": scorer.load_error,
                    "advisory_only": True,
                    "routing_authority": "deterministic_sre87_rules",
                    "eligible_count": len(eligible),
                    "assessments": [value.to_dict() for value in assessments],
                },
                indent=2,
            )
        )
        return

    cycle = SRE87ControlCycle(config)
    code, summary = cycle.run(
        dry_run=args.dry_run,
        now=_optional_datetime(args.now),
    )
    print(json.dumps(summary.to_dict(), indent=2))
    raise SystemExit(int(code))


def _optional_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("--now must include a timezone, such as 2026-08-05T19:00:00-05:00")
    return parsed


if __name__ == "__main__":
    main()
