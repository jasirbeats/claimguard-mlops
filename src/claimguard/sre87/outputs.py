from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

from claimguard.sre87.models import RunSummary


class RunOutputWriter:
    def __init__(self, logs_root: Path) -> None:
        self.logs_root = logs_root

    def write(self, summary: RunSummary, events: list[str], now: datetime) -> RunSummary:
        run_dir = self.logs_root / now.strftime("%Y-%m-%d")
        run_dir.mkdir(parents=True, exist_ok=True)
        stem = f"run_{summary.run_id}"
        json_path = run_dir / f"{stem}.json"
        csv_path = run_dir / f"{stem}.csv"
        log_path = run_dir / f"{stem}.log"

        summary.output_json = str(json_path)
        summary.output_csv = str(csv_path)
        summary.output_log = str(log_path)
        json_path.write_text(
            json.dumps(summary.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
        self._write_csv(csv_path, summary)
        log_path.write_text("\n".join(events) + "\n", encoding="utf-8")
        return summary

    @staticmethod
    def _write_csv(path: Path, summary: RunSummary) -> None:
        fieldnames = [
            "claim_tracking_id",
            "current_status",
            "ai_risk_probability",
            "ai_risk_level",
            "ai_priority_score",
            "ai_likely_failure_layer",
            "ai_advisory_only",
            "assigned_processing_layer",
            "endpoint_name",
            "request_mode",
            "request_id",
            "response_code",
            "accepted",
            "dry_run",
            "post_recovery_status",
            "execution_timestamp",
        ]
        risk_by_id = {
            assessment.claim_tracking_id: assessment for assessment in summary.risk_assessments
        }
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fieldnames)
            writer.writeheader()
            for result in summary.recovery_results:
                risk = risk_by_id.get(result.claim_tracking_id)
                writer.writerow(
                    {
                        "claim_tracking_id": result.claim_tracking_id,
                        "current_status": result.source_status,
                        "ai_risk_probability": risk.probability if risk else "",
                        "ai_risk_level": risk.risk_level if risk else "",
                        "ai_priority_score": risk.priority_score if risk else "",
                        "ai_likely_failure_layer": (risk.likely_failure_layer if risk else ""),
                        "ai_advisory_only": risk.advisory_only if risk else "",
                        "assigned_processing_layer": result.assigned_layer,
                        "endpoint_name": result.endpoint_name,
                        "request_mode": result.request_mode,
                        "request_id": result.request_id,
                        "response_code": result.response_code,
                        "accepted": result.accepted,
                        "dry_run": result.dry_run,
                        "post_recovery_status": result.post_recovery_status,
                        "execution_timestamp": result.execution_timestamp,
                    }
                )
