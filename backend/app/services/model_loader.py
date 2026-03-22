"""Model Loader — loads pre-trained benchmark model weights from the
Specific_Models_Final directory and instantiates the correct PyTorch / sklearn model.

Maintains an in-memory cache so repeated requests are fast.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import torch
import numpy as np

from app.config import settings
from app.models.traditional import TraditionalModelWrapper

try:
    from app.models.benchmark_models import (
        SiameseLSTMPolyPredict,
        SiameseRegressorGraph,
        BiLSTMRegressorSMILES,
        LSTMSiamesePolyPredict,
        VAERegressor,
    )
    HAS_BENCHMARK = True
except ImportError:
    HAS_BENCHMARK = False

# ──────────────────────────────────────────────────────────────────────
CACHE: dict[str, Any] = {}

DEVICE = settings.DEVICE


def _benchmark_path(folder: str, filename: str) -> Path:
    return Path(settings.BENCHMARK_MODELS_DIR) / folder / filename


# ──────────────────────────────────────────────────────────────────────
#  Benchmark model loaders (from Specific_Models_Final/)
# ──────────────────────────────────────────────────────────────────────
def _load_siamese_lstm() -> SiameseLSTMPolyPredict:
    if not HAS_BENCHMARK:
        raise ImportError("torch_geometric is required for benchmark graph models")
    model = SiameseLSTMPolyPredict()
    path = _benchmark_path("Siamese_plus_LSTM", "saved_models/best_siamese_bilstm_polypred.pth")
    model.load_state_dict(torch.load(path, map_location=DEVICE, weights_only=True))
    model.to(DEVICE).eval()
    return model


def _load_siamese_regression() -> SiameseRegressorGraph:
    if not HAS_BENCHMARK:
        raise ImportError("torch_geometric is required for benchmark graph models")
    model = SiameseRegressorGraph()
    path = _benchmark_path("Siamese_Regression", "siamese_regression_model.pth")
    model.load_state_dict(torch.load(path, map_location=DEVICE, weights_only=True))
    model.to(DEVICE).eval()
    return model


def _load_siamese_bayesian() -> SiameseRegressorGraph:
    if not HAS_BENCHMARK:
        raise ImportError("torch_geometric is required for benchmark graph models")
    model = SiameseRegressorGraph()
    path = _benchmark_path("Siamese_plus_Bayesian", "siamese_bayesian_model.pth")
    model.load_state_dict(torch.load(path, map_location=DEVICE, weights_only=True))
    model.to(DEVICE).eval()
    return model


def _load_lstm_bayesian() -> BiLSTMRegressorSMILES:
    if not HAS_BENCHMARK:
        raise ImportError("benchmark_models module is required")
    model = BiLSTMRegressorSMILES()
    path = _benchmark_path("LSTM_plus_Bayesian", "lstm_bayesian_model.pth")
    model.load_state_dict(torch.load(path, map_location=DEVICE, weights_only=True))
    model.to(DEVICE).eval()
    return model


def _load_lstm_siamese_bayesian() -> LSTMSiamesePolyPredict:
    if not HAS_BENCHMARK:
        raise ImportError("torch_geometric is required for benchmark graph models")
    model = LSTMSiamesePolyPredict()
    path = _benchmark_path("LSTM_plus_Siamese_plus_Bayesian", "lstm_siamese_bayesian_model.pth")
    model.load_state_dict(torch.load(path, map_location=DEVICE, weights_only=True))
    model.to(DEVICE).eval()
    return model


def _load_standalone_lstm() -> BiLSTMRegressorSMILES:
    if not HAS_BENCHMARK:
        raise ImportError("benchmark_models module is required")
    model = BiLSTMRegressorSMILES()
    path = _benchmark_path("Long_Short_Term_Memory", "lstm_model.pth")
    model.load_state_dict(torch.load(path, map_location=DEVICE, weights_only=True))
    model.to(DEVICE).eval()
    return model


def _load_benchmark_ensemble() -> TraditionalModelWrapper:
    p1 = _benchmark_path("Ensemble_Methods", "best_ensemble_r1.joblib")
    p2 = _benchmark_path("Ensemble_Methods", "best_ensemble_r2.joblib")
    return TraditionalModelWrapper.load(p1, p2, name="ensemble_methods")

def _load_benchmark_decision_tree() -> TraditionalModelWrapper:
    p1 = _benchmark_path("Decision_Tree", "best_dt_r1.joblib")
    p2 = _benchmark_path("Decision_Tree", "best_dt_r2.joblib")
    return TraditionalModelWrapper.load(p1, p2, name="decision_tree")

def _load_benchmark_random_forest() -> TraditionalModelWrapper:
    p1 = _benchmark_path("Random_Forest", "best_rf_r1.joblib")
    p2 = _benchmark_path("Random_Forest", "best_rf_r2.joblib")
    return TraditionalModelWrapper.load(p1, p2, name="random_forest")


def _load_benchmark_autoencoder() -> VAERegressor:
    if not HAS_BENCHMARK:
        raise ImportError("torch_geometric is required for benchmark graph models")
    model = VAERegressor()
    path = _benchmark_path("Autoencoders", "vae_model.pth")
    model.load_state_dict(torch.load(path, map_location=DEVICE, weights_only=True))
    model.to(DEVICE).eval()
    return model


# ──────────────────────────────────────────────────────────────────────
#  Public API
# ──────────────────────────────────────────────────────────────────────
_LOADERS = {
    # Benchmark models (pre-trained weights in Specific_Models_Final/)
    "siamese_lstm": _load_siamese_lstm,
    "siamese_regression": _load_siamese_regression,
    "siamese_bayesian": _load_siamese_bayesian,
    "lstm_bayesian": _load_lstm_bayesian,
    "lstm_siamese_bayesian": _load_lstm_siamese_bayesian,
    "standalone_lstm": _load_standalone_lstm,
    "ensemble_methods": _load_benchmark_ensemble,
    "decision_tree": _load_benchmark_decision_tree,
    "random_forest": _load_benchmark_random_forest,
    "autoencoder": _load_benchmark_autoencoder,
}


def get_model(model_type: str) -> Any:
    """Load (cached) model by its type key."""
    if model_type in CACHE:
        return CACHE[model_type]
    loader = _LOADERS.get(model_type)
    if loader is None:
        raise ValueError(f"Unknown model type: {model_type}. Available: {list(_LOADERS)}")
    model = loader()
    CACHE[model_type] = model
    return model


def available_models() -> list[str]:
    return list(_LOADERS.keys())


def clear_cache():
    CACHE.clear()
