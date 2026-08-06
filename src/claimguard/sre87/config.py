from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from claimguard.config import PROJECT_ROOT


@dataclass(frozen=True)
class ThresholdConfig:
    claim_age_hours: float
    success_status: int
    eligible_statuses: tuple[int, ...]
    include_status_660: bool

    @property
    def effective_eligible_statuses(self) -> tuple[int, ...]:
        statuses = list(self.eligible_statuses)
        if self.include_status_660 and 660 not in statuses:
            statuses.append(660)
        return tuple(statuses)


@dataclass(frozen=True)
class PathConfig:
    claims_file: Path
    runtime_root: Path

    @property
    def state_file(self) -> Path:
        return self.runtime_root / "state" / "last_run.json"

    @property
    def pause_file(self) -> Path:
        return self.runtime_root / "state" / "paused.flag"

    @property
    def logs_root(self) -> Path:
        return self.runtime_root / "logs"

    @property
    def incidents_file(self) -> Path:
        return self.runtime_root / "incidents" / "incidents.jsonl"


@dataclass(frozen=True)
class AIConfig:
    enabled: bool
    model_path: Path
    metadata_path: Path


@dataclass(frozen=True)
class IncidentConfig:
    enabled: bool
    assignment_group: str


@dataclass(frozen=True)
class SRE87Config:
    environment: str
    thresholds: ThresholdConfig
    paths: PathConfig
    incident: IncidentConfig
    ai: AIConfig

    @classmethod
    def load(cls, path: Path) -> SRE87Config:
        config_path = path if path.is_absolute() else PROJECT_ROOT / path
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        return cls.from_dict(payload)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> SRE87Config:
        thresholds = payload["thresholds"]
        paths = payload["paths"]
        incident = payload.get("incident", {})
        ai = payload.get("ai", {})
        return cls(
            environment=str(payload.get("environment", "DEMO")),
            thresholds=ThresholdConfig(
                claim_age_hours=float(thresholds.get("claim_age_hours", 2)),
                success_status=int(thresholds.get("success_status", 300)),
                eligible_statuses=tuple(
                    int(value)
                    for value in thresholds.get("eligible_statuses", [655, 665, 800, 850])
                ),
                include_status_660=bool(thresholds.get("include_status_660", False)),
            ),
            paths=PathConfig(
                claims_file=_project_path(str(paths["claims_file"])),
                runtime_root=_project_path(str(paths["runtime_root"])),
            ),
            incident=IncidentConfig(
                enabled=bool(incident.get("enabled", True)),
                assignment_group=str(incident.get("assignment_group", "DEMO_SRE_SUPPORT")),
            ),
            ai=AIConfig(
                enabled=bool(ai.get("enabled", False)),
                model_path=_project_path(
                    str(ai.get("model_path", "artifacts/sre87_risk_model.joblib"))
                ),
                metadata_path=_project_path(
                    str(
                        ai.get(
                            "metadata_path",
                            "artifacts/sre87_risk_model_metadata.json",
                        )
                    )
                ),
            ),
        )


def _project_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path
