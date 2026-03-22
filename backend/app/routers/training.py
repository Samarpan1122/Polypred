"""Endpoints for model training, progress tracking, and results."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.services.training_service import (
    start_training, get_progress, get_results, list_jobs,
)
from app.models.schemas import TrainRequest

router = APIRouter(prefix="/api/training", tags=["training"])


@router.post("/start")
async def launch(req: TrainRequest):
    job_id = start_training(req)
    return {"job_id": job_id, "status": "queued"}


@router.get("/jobs")
async def jobs():
    return list_jobs()


@router.get("/progress/{job_id}")
async def progress(job_id: str):
    p = get_progress(job_id)
    if p is None:
        return JSONResponse({"error": "Job not found"}, 404)
    return p.model_dump()


@router.get("/results/{job_id}")
async def results(job_id: str):
    r = get_results(job_id)
    if r is None:
        return JSONResponse({"error": "Results not found"}, 404)
    return r


@router.get("/models/available")
async def available_models():
    """Return list of trainable model types grouped by category.
    Only the 10 models that have pre-trained weights in Specific_Models_Final.
    """
    return {
        "traditional": [
            {"id": "decision_tree", "name": "Decision Tree", "description": "CART decision tree regressor (max_depth=10)"},
            {"id": "random_forest", "name": "Random Forest", "description": "Ensemble of 200 decision trees (max_depth=15)"},
            {"id": "ensemble_methods", "name": "Ensemble Methods", "description": "Gradient Boosting — best sklearn ensemble from benchmark"},
        ],
        "graph_based": [
            {"id": "siamese_lstm", "name": "Siamese + LSTM", "description": "Siamese GAT + BiLSTM — 4-layer GAT with bidirectional LSTM"},
            {"id": "siamese_regression", "name": "Siamese Regression", "description": "Shared 2-layer GAT arms with direct regression head"},
            {"id": "siamese_bayesian", "name": "Siamese + Bayesian", "description": "Siamese GNN with Bayesian-optimized hyperparameters"},
            {"id": "lstm_siamese_bayesian", "name": "LSTM + Siamese + Bayesian", "description": "Hybrid graph-LSTM combining GAT with BiLSTM and Bayesian tuning"},
        ],
        "lstm": [
            {"id": "lstm_bayesian", "name": "LSTM + Bayesian", "description": "Character-level SMILES BiLSTM with Bayesian-optimized architecture"},
            {"id": "standalone_lstm", "name": "Standalone LSTM", "description": "Bidirectional LSTM on SMILES character sequences"},
        ],
        "autoencoder": [
            {"id": "autoencoder", "name": "VAE Autoencoder", "description": "Graph VAE with GCN encoder and regression head for r₁/r₂ prediction"},
        ],
    }
