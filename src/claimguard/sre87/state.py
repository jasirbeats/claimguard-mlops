from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class RunStateStore:
    def __init__(self, state_file: Path, pause_file: Path) -> None:
        self.state_file = state_file
        self.pause_file = pause_file

    def load(self) -> dict[str, Any]:
        if not self.state_file.exists():
            return {"submitted_ids": []}
        return json.loads(self.state_file.read_text(encoding="utf-8"))

    def save(self, *, run_id: str, completed_at: str, submitted_ids: list[str]) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "last_run_id": run_id,
            "last_run_time": completed_at,
            "submitted_ids": submitted_ids,
        }
        self.state_file.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def is_paused(self) -> bool:
        return self.pause_file.exists()

    def pause(self) -> None:
        self.pause_file.parent.mkdir(parents=True, exist_ok=True)
        self.pause_file.write_text("paused\n", encoding="utf-8")

    def resume(self) -> None:
        self.pause_file.unlink(missing_ok=True)
