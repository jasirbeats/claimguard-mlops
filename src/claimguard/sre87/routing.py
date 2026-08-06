from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Route:
    status: int
    assigned_layer: str
    endpoint_name: str
    request_mode: str


ROUTES: dict[int, Route] = {
    655: Route(655, "CDR Persistence", "persistence-reprocessor", "bulk-json"),
    665: Route(665, "CDR Persistence", "persistence-reprocessor", "bulk-json"),
    660: Route(660, "CDR Persistence", "persistence-reprocessor", "bulk-json"),
    800: Route(800, "Claim Intake / State Manager", "state-manager-reprocessor", "single-query"),
    850: Route(850, "Claim Intake / CBO", "cbo-reprocessor", "single-json"),
}


def route_for_status(status: int) -> Route:
    try:
        return ROUTES[status]
    except KeyError as exc:
        raise ValueError(f"No deterministic SRE 87 route for status {status}") from exc
