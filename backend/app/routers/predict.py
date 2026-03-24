"""Prediction router - /api/predict endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.prediction_service import predict, predict_multi, predict_all
from app.services.model_loader import available_models
from app.models.feature_engineering import (
    compute_eda_descriptors,
    smiles_to_morgan_fp,
)

router = APIRouter(prefix="/api/predict", tags=["predict"])


# ──────────────────────────────────────────────────────────────────────
#  Schemas
# ──────────────────────────────────────────────────────────────────────
class PredictRequest(BaseModel):
    smiles_a: str = Field(..., description="SMILES for monomer A")
    smiles_b: str = Field(..., description="SMILES for monomer B")
    model: str = Field(..., description="Model type key")


class PredictMultiRequest(BaseModel):
    smiles_a: str
    smiles_b: str
    models: list[str] = Field(default_factory=list, description="Model keys (empty = all)")


class PredictResponse(BaseModel):
    model: str
    r1: float | None = None
    r2: float | None = None
    latency_ms: float | None = None
    error: str | None = None


class MoleculeInfo(BaseModel):
    smiles: str
    valid: bool
    descriptors: dict | None = None
    fingerprint_bits_set: int | None = None


# ──────────────────────────────────────────────────────────────────────
#  Endpoints
# ──────────────────────────────────────────────────────────────────────
@router.post("/single", response_model=PredictResponse)
async def predict_single(req: PredictRequest):
    if req.model not in available_models():
        raise HTTPException(400, f"Unknown model: {req.model}")
    result = predict(req.model, req.smiles_a, req.smiles_b)
    return PredictResponse(**result)


@router.post("/multi", response_model=list[PredictResponse])
async def predict_multiple(req: PredictMultiRequest):
    models = req.models if req.models else [
        m for m in available_models() if m not in {
            "autoencoder_standard", "autoencoder_denoising", "vae"
        }
    ]
    results = predict_multi(models, req.smiles_a, req.smiles_b)
    return [PredictResponse(**r) for r in results]


@router.post("/all", response_model=list[PredictResponse])
async def predict_all_models(req: PredictMultiRequest):
    results = predict_all(req.smiles_a, req.smiles_b)
    return [PredictResponse(**r) for r in results]


@router.post("/validate", response_model=MoleculeInfo)
async def validate_molecule(smiles: str):
    fp = smiles_to_morgan_fp(smiles)
    descs = compute_eda_descriptors(smiles)
    return MoleculeInfo(
        smiles=smiles,
        valid=fp is not None,
        descriptors=descs,
        fingerprint_bits_set=int(fp.sum()) if fp is not None else None,
    )
