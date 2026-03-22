"""Compare router — /api/compare endpoints for multi-model comparison."""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.prediction_service import predict_multi, predict_all, MODEL_CATEGORIES, ENCODER_MODELS
from app.services.model_loader import available_models

router = APIRouter(prefix="/api/compare", tags=["compare"])


class CompareRequest(BaseModel):
    smiles_a: str
    smiles_b: str
    models: list[str] = Field(default_factory=list, description="Models to compare (empty = all)")
    category: str | None = Field(None, description="Filter by category: deep_learning | traditional_ml")


class CompareResult(BaseModel):
    model: str
    r1: float | None = None
    r2: float | None = None
    latency_ms: float | None = None
    error: str | None = None


class CompareResponse(BaseModel):
    results: list[CompareResult]
    summary: dict


@router.post("/", response_model=CompareResponse)
async def compare_models(req: CompareRequest):
    # Determine model list
    if req.models:
        model_list = req.models
    elif req.category and req.category in MODEL_CATEGORIES:
        model_list = sorted(MODEL_CATEGORIES[req.category])
    else:
        model_list = [m for m in available_models() if m not in ENCODER_MODELS]

    raw = predict_multi(model_list, req.smiles_a, req.smiles_b)
    results = [CompareResult(**r) for r in raw]

    # Summary stats
    valid = [r for r in results if r.error is None and r.r1 is not None]
    if valid:
        r1_vals = [r.r1 for r in valid]
        r2_vals = [r.r2 for r in valid if r.r2 is not None]
        summary = {
            "num_models": len(valid),
            "r1_mean": round(sum(r1_vals) / len(r1_vals), 4),
            "r1_min": round(min(r1_vals), 4),
            "r1_max": round(max(r1_vals), 4),
            "r2_mean": round(sum(r2_vals) / len(r2_vals), 4) if r2_vals else None,
            "r2_min": round(min(r2_vals), 4) if r2_vals else None,
            "r2_max": round(max(r2_vals), 4) if r2_vals else None,
            "fastest_model": min(valid, key=lambda x: x.latency_ms or float("inf")).model,
            "avg_latency_ms": round(
                sum(r.latency_ms for r in valid if r.latency_ms) / len(valid), 2
            ),
        }
    else:
        summary = {"num_models": 0, "error": "All models failed"}

    return CompareResponse(results=results, summary=summary)
