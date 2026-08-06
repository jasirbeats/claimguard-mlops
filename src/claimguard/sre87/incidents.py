from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from claimguard.sre87.models import IncidentRecord


class MockIncidentService:
    """Writes ServiceNow-shaped incidents to JSONL for the public demo."""

    def __init__(self, path: Path, assignment_group: str, enabled: bool = True) -> None:
        self.path = path
        self.assignment_group = assignment_group
        self.enabled = enabled

    def create(
        self,
        *,
        run_id: str,
        incident_type: str,
        summary: str,
        unresolved_ids: list[str],
        created_at: datetime,
    ) -> IncidentRecord | None:
        if not self.enabled:
            return None
        record = IncidentRecord(
            incident_id=f"DEMO{uuid4().hex[:8].upper()}",
            run_id=run_id,
            incident_type=incident_type,
            assignment_group=self.assignment_group,
            summary=summary,
            unresolved_ids=unresolved_ids,
            created_at=created_at.isoformat(),
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record.to_dict()) + "\n")
        return record
