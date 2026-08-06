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
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fieldnames)
            writer.writeheader()
            for result in summary.recovery_results:
                writer.writerow(
                    {
                        "claim_tracking_id": result.claim_tracking_id,
                        "current_status": result.source_status,
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
