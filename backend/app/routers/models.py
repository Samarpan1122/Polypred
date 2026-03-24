"""Models info router - /api/models endpoints."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.model_loader import available_models
from app.services.prediction_service import MODEL_CATEGORIES, ENCODER_MODELS

router = APIRouter(prefix="/api/models", tags=["models"])


class ModelInfo(BaseModel):
    name: str
    category: str
    description: str
    input_type: str
    output_type: str


MODEL_DESCRIPTIONS = {
    # ── Siamese / Graph-based ──────────────────────────────────────────────
    "siamese_lstm": "Siamese GAT + BiLSTM - main PolyPredict model with 4-layer GAT and bidirectional LSTM fusion",
    "siamese_regression": "Siamese Regression - shared 2-layer GAT arms with direct prediction head",
    "siamese_bayesian": "Siamese + Bayesian - Siamese GNN with Bayesian-tuned hyperparameters",
    "lstm_siamese_bayesian": "LSTM + Siamese + Bayesian - hybrid graph-LSTM model combining GAT with BiLSTM",
    # ── LSTM-based ────────────────────────────────────────────────────────
    "lstm_bayesian": "LSTM + Bayesian - character-level SMILES BiLSTM with Bayesian-optimized architecture",
    "standalone_lstm": "Standalone LSTM - bidirectional LSTM on SMILES character sequences",
    # ── Traditional ML ────────────────────────────────────────────────────
    "decision_tree": "Decision Tree Regressor (max_depth=10) - interpretable tree-based model",
    "random_forest": "Random Forest (200 trees, max_depth=15) - ensemble of decision trees",
    "ensemble_methods": "Ensemble Methods - best sklearn ensemble from comparative benchmark (GradientBoosting)",
    # ── Autoencoder ───────────────────────────────────────────────────────
    "autoencoder": "VAE Regressor - Graph VAE with GCN encoder and regression head for r₁/r₂ prediction",
}

INPUT_TYPES = {
    "siamese_lstm": "Molecular graphs (pair, 58 node + 13 edge + 7 global features)",
    "siamese_regression": "Molecular graphs (pair, 58 node features)",
    "siamese_bayesian": "Molecular graphs (pair, 58 node features)",
    "lstm_siamese_bayesian": "Molecular graphs (pair)",
    "lstm_bayesian": "SMILES strings (character tokens, max_len=150)",
    "standalone_lstm": "SMILES strings (character tokens, max_len=150)",
    "decision_tree": "Graph-derived flat features (248-dim)",
    "random_forest": "Graph-derived flat features (248-dim)",
    "ensemble_methods": "Graph-derived flat features (248-dim)",
    "autoencoder": "Molecular graph (GCN encoder, 58 node features)",
}
_default_input = "Graph-derived flat features (248-dim)"


def _get_category(name: str) -> str:
    for cat, members in MODEL_CATEGORIES.items():
        if name in members:
            return cat
    if name in ENCODER_MODELS:
        return "encoder"
    return "unknown"


@router.get("/", response_model=list[ModelInfo])
async def list_models():
    return [
        ModelInfo(
            name=m,
            category=_get_category(m),
            description=MODEL_DESCRIPTIONS.get(m, ""),
            input_type=INPUT_TYPES.get(m, _default_input),
            output_type="(r₁, r₂)" if "mimo" in m or m in {
                "lstm_large", "lstm_optimized",
                "decision_tree", "random_forest", "gradient_boosting",
                "xgboost", "extra_trees", "adaboost",
                "linear_regression", "ridge", "lasso", "elasticnet", "knn", "svm",
                "siamese_lstm", "siamese_regression", "siamese_bayesian",
                "lstm_bayesian", "lstm_siamese_bayesian", "standalone_lstm",
                "ensemble_methods",
            } else "latent / reconstruction",
        )
        for m in available_models()
    ]


@router.get("/categories")
async def list_categories():
    return {
        "deep_learning": sorted(MODEL_CATEGORIES["deep_learning"]),
        "traditional_ml": sorted(MODEL_CATEGORIES["traditional_ml"]),
        "encoder": sorted(ENCODER_MODELS),
        "benchmark": sorted(MODEL_CATEGORIES.get("benchmark", set())),
    }
