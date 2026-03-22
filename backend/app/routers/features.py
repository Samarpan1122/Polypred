"""Endpoints for featurization and feature reduction."""

from fastapi import APIRouter
from app.services.feature_service import (
    featurize_dataset, list_feature_sets, get_feature_set_info,
    get_feature_correlation, load_feature_set,
)
from app.models.schemas import FeaturizeRequest, FeatureReductionMethod

router = APIRouter(prefix="/api/features", tags=["features"])


@router.post("/featurize")
async def featurize(req: FeaturizeRequest):
    result = featurize_dataset(
        dataset_id=req.dataset_id,
        smiles_col_a=req.smiles_col_a,
        smiles_col_b=req.smiles_col_b,
        method=req.method,
        reduction=req.reduction,
        reduction_params=req.reduction_params,
    )
    return result


@router.get("/")
async def list_all():
    return list_feature_sets()


@router.get("/{feature_set_id}")
async def get_info(feature_set_id: str):
    return get_feature_set_info(feature_set_id)


@router.get("/{feature_set_id}/correlation")
async def correlation(feature_set_id: str, max_features: int = 50):
    return get_feature_correlation(feature_set_id, max_features)


@router.get("/{feature_set_id}/stats")
async def feature_stats(feature_set_id: str):
    X, _, meta = load_feature_set(feature_set_id)
    import numpy as np
    return {
        "id": feature_set_id,
        "shape": list(X.shape),
        "mean": X.mean(axis=0)[:20].tolist(),
        "std": X.std(axis=0)[:20].tolist(),
        "min": X.min(axis=0)[:20].tolist(),
        "max": X.max(axis=0)[:20].tolist(),
        "sparsity": float((X == 0).sum() / X.size),
    }
