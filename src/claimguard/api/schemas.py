from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ClaimRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_tracking_id: str = Field(min_length=3, max_length=100)
    claim_type: Literal["professional", "institutional", "dental", "pharmacy"]
    state_code: str = Field(pattern=r"^[A-Z]{2}$")
    provider_type: Literal["hospital", "clinic", "specialist", "pharmacy", "laboratory"]
    source_system: Literal["portal", "edi", "batch", "api"]
    claim_amount: float = Field(ge=0, le=10_000_000)
    retry_count: int = Field(ge=0, le=20)
    queue_depth: int = Field(ge=0, le=100_000)
    processing_duration_seconds: int = Field(ge=0, le=604_800)
    previous_failure_count: int = Field(ge=0, le=100)
    hour_of_day: int = Field(ge=0, le=23)
    day_of_week: int = Field(ge=0, le=6)
    procedure_count: int = Field(ge=1, le=1_000)
    endpoint_response_code: str = Field(pattern=r"^[1-5][0-9]{2}$")


class PredictionResponse(BaseModel):
    claim_tracking_id: str
    prediction: Literal["low_risk", "high_risk"]
    failure_probability: float
    model_name: str
    model_version: str
    threshold: float
