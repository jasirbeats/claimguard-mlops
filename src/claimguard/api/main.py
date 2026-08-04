from __future__ import annotations

from fastapi import FastAPI, HTTPException, status

from claimguard import __version__
from claimguard.api.model_service import (
    ModelUnavailableError,
    configured_model_path,
    load_model_bundle,
    predict,
)
from claimguard.api.schemas import ClaimRequest, PredictionResponse

app = FastAPI(
    title="ClaimGuard AI",
    description="Predicts whether a synthetic claim workflow is at risk of becoming stuck.",
    version=__version__,
)


@app.get("/health/live")
def liveness() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/health/ready")
def readiness() -> dict[str, str]:
    try:
        load_model_bundle()
    except ModelUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return {"status": "ready"}


@app.get("/model/info")
def model_info() -> dict[str, object]:
    try:
        bundle = load_model_bundle()
    except ModelUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "model_name": bundle["model_name"],
        "model_version": bundle["model_version"],
        "trained_at": bundle.get("trained_at"),
        "threshold": bundle["threshold"],
        "features": bundle["features"],
        "artifact_path": str(configured_model_path()),
    }


@app.post("/predict", response_model=PredictionResponse)
def predict_claim(request: ClaimRequest) -> PredictionResponse:
    try:
        result = predict(request.model_dump())
    except ModelUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return PredictionResponse(**result)
