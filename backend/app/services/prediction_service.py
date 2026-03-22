"""Prediction service — runs one or many models on a monomer pair."""

from __future__ import annotations

import time
import numpy as np
import torch
from typing import Any

from app.config import settings
from app.services.model_loader import get_model, available_models, DEVICE
from app.models.feature_engineering import (
    smiles_to_morgan_fp,
    pair_fingerprints,
    pair_flat_features,
    pair_flat_features_ensemble,
    smiles_to_graph,
)
from app.models.siamese import build_pair_features

try:
    from app.models.gat import graph_dict_to_pyg
    HAS_GAT = True
except ImportError:
    HAS_GAT = False

try:
    from app.models.benchmark_models import (
        graph_dict_to_single_pyg,
        encode_smiles,
        SiameseLSTMPolyPredict,
        SiameseRegressorGraph,
        BiLSTMRegressorSMILES,
        LSTMSiamesePolyPredict,
    )
    from torch_geometric.data import Batch
    HAS_BENCHMARK = True
except ImportError:
    HAS_BENCHMARK = False


# ──────────────────────────────────────────────────────────────────────
#  Category helpers
# ──────────────────────────────────────────────────────────────────────
ENCODER_MODELS = {"autoencoder_standard", "autoencoder_denoising", "vae"}

# Benchmark categories
BENCHMARK_GRAPH_MODELS = {
    "siamese_lstm", "siamese_regression", "siamese_bayesian", "lstm_siamese_bayesian",
    "autoencoder",
}
BENCHMARK_SMILES_MODELS = {"lstm_bayesian", "standalone_lstm"}
BENCHMARK_TRADITIONAL_MODELS = {"ensemble_methods", "decision_tree", "random_forest"}
BENCHMARK_MODELS = BENCHMARK_GRAPH_MODELS | BENCHMARK_SMILES_MODELS | BENCHMARK_TRADITIONAL_MODELS

MODEL_CATEGORIES = {
    "benchmark": BENCHMARK_MODELS,
}


# ──────────────────────────────────────────────────────────────────────
#  Single-model prediction
# ──────────────────────────────────────────────────────────────────────

# ── Benchmark prediction functions ────────────────────────────────────
def _predict_benchmark_graph(model_name: str, smiles_a: str, smiles_b: str) -> dict:
    """Benchmark Siamese graph models — separate PyG Data per monomer."""
    if not HAS_BENCHMARK:
        return {"error": "torch_geometric not installed"}
    model = get_model(model_name)
    ga = smiles_to_graph(smiles_a)
    gb = smiles_to_graph(smiles_b)
    if ga is None or gb is None:
        return {"error": "Invalid SMILES"}
    dA = graph_dict_to_single_pyg(ga, device=DEVICE)
    dB = graph_dict_to_single_pyg(gb, device=DEVICE)
    # Add batch attribute for single-sample inference
    dA.batch = torch.zeros(dA.x.size(0), dtype=torch.long, device=DEVICE)
    dB.batch = torch.zeros(dB.x.size(0), dtype=torch.long, device=DEVICE)
    with torch.no_grad():
        out = model(dA, dB).cpu().numpy().flatten()
    return {"r1": float(out[0]), "r2": float(out[1])}


def _predict_benchmark_smiles(model_name: str, smiles_a: str, smiles_b: str) -> dict:
    """Benchmark LSTM models using SMILES token sequences."""
    if not HAS_BENCHMARK:
        return {"error": "benchmark_models not available"}
    model = get_model(model_name)
    tokA = encode_smiles(smiles_a).unsqueeze(0).to(DEVICE)
    tokB = encode_smiles(smiles_b).unsqueeze(0).to(DEVICE)
    with torch.no_grad():
        out = model(tokA, tokB).cpu().numpy().flatten()
    return {"r1": float(out[0]), "r2": float(out[1])}


def _predict_benchmark_traditional(model_name: str, smiles_a: str, smiles_b: str) -> dict:
    """Benchmark ensemble model — uses 130-dim flat features (mean-pool + global)."""
    wrapper = get_model(model_name)
    flat = pair_flat_features_ensemble(smiles_a, smiles_b)
    if flat is None:
        return {"error": "Invalid SMILES"}
    preds = wrapper.predict(flat.reshape(1, -1))
    return {"r1": float(preds[0, 0]), "r2": float(preds[0, 1])}


_DISPATCH = {}
for name in BENCHMARK_GRAPH_MODELS:
    _DISPATCH[name] = _predict_benchmark_graph
for name in BENCHMARK_SMILES_MODELS:
    _DISPATCH[name] = _predict_benchmark_smiles
for name in BENCHMARK_TRADITIONAL_MODELS:
    _DISPATCH[name] = _predict_benchmark_traditional


# ──────────────────────────────────────────────────────────────────────
#  Public API
# ──────────────────────────────────────────────────────────────────────
def predict(model_name: str, smiles_a: str, smiles_b: str) -> dict:
    """Run a single model and return prediction + timing."""
    fn = _DISPATCH.get(model_name)
    if fn is None:
        return {"error": f"Unknown model: {model_name}"}
    t0 = time.perf_counter()
    try:
        result = fn(model_name, smiles_a, smiles_b)
    except Exception as e:
        result = {"error": f"Failed to run model: {str(e)}"}
    elapsed = time.perf_counter() - t0
    result["model"] = model_name
    result["latency_ms"] = round(elapsed * 1000, 2)
    return result


def predict_multi(model_names: list[str], smiles_a: str, smiles_b: str) -> list[dict]:
    """Run multiple models and return all results."""
    return [predict(name, smiles_a, smiles_b) for name in model_names]


def predict_all(smiles_a: str, smiles_b: str) -> list[dict]:
    """Run every available prediction model."""
    pred_models = [m for m in available_models() if m not in ENCODER_MODELS]
    return predict_multi(pred_models, smiles_a, smiles_b)
