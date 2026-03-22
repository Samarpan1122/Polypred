"""Feature engineering service — featurize datasets, apply reductions."""

from __future__ import annotations

import os
import uuid
import json
import pickle
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.feature_selection import (
    VarianceThreshold,
    mutual_info_regression,
    SelectKBest,
    f_regression,
)

from app.models.schemas import FeaturizationMethod, FeatureReductionMethod
from app.models.feature_engineering import (
    smiles_to_morgan_fp,
    pair_flat_features,
    compute_rdkit_descriptors,
    compute_3d_autocorr,
    smiles_to_graph,
    graph_to_flat_features,
)
from app.services.dataset_service import load_dataframe, DATA_DIR

FEATURE_DIR = Path(os.getenv("FEATURE_DIR", "/tmp/polypred_features"))
FEATURE_DIR.mkdir(parents=True, exist_ok=True)


def featurize_dataset(
    dataset_id: str,
    smiles_col_a: str,
    smiles_col_b: str,
    method: FeaturizationMethod,
    reduction: FeatureReductionMethod = FeatureReductionMethod.NONE,
    reduction_params: dict[str, Any] | None = None,
) -> dict:
    """Featurize every row of a dataset and optionally reduce features."""
    df = load_dataframe(dataset_id)
    reduction_params = reduction_params or {}

    # ── 1. Generate raw features ──────────────────────────
    features = []
    valid_indices = []
    feature_names: list[str] = []

    # If method is ALL, iterate each real method and concatenate
    if method == FeaturizationMethod.ALL:
        real_methods = [m for m in FeaturizationMethod if m != FeaturizationMethod.ALL]
    else:
        real_methods = [method]

    for i, row in df.iterrows():
        sa, sb = str(row[smiles_col_a]), str(row[smiles_col_b])
        parts = []
        ok = True
        for m in real_methods:
            feat = _compute_features(sa, sb, m)
            if feat is not None:
                parts.append(feat)
            else:
                ok = False
                break
        if ok and parts:
            features.append(np.concatenate(parts))
            valid_indices.append(i)

    if not features:
        return {"error": "No valid features could be computed"}

    X = np.array(features, dtype=np.float32)
    n_samples, n_raw = X.shape

    # Generate feature names
    if method == FeaturizationMethod.MORGAN_FP:
        feature_names = [f"fp_{i}" for i in range(n_raw)]
    elif method == FeaturizationMethod.RDKIT_DESCRIPTORS:
        feature_names = [f"desc_{i}" for i in range(n_raw)]
    elif method in (FeaturizationMethod.FLAT_GRAPH, FeaturizationMethod.GRAPH_FEATURES):
        feature_names = [f"gf_{i}" for i in range(n_raw)]
    else:
        feature_names = [f"feat_{i}" for i in range(n_raw)]

    # ── 2. Handle NaN / Inf ───────────────────────────────
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

    # ── 3. Feature reduction ──────────────────────────────
    reduction_info: dict[str, Any] = {"method": reduction.value}

    if reduction == FeatureReductionMethod.CORRELATION_FILTER:
        threshold = reduction_params.get("threshold", 0.95)
        corr = np.corrcoef(X.T)
        corr = np.nan_to_num(corr)
        upper = np.triu(np.abs(corr), k=1)
        drop = [i for i in range(upper.shape[1]) if any(upper[:, i] > threshold)]
        keep = [i for i in range(X.shape[1]) if i not in drop]
        X = X[:, keep]
        feature_names = [feature_names[i] for i in keep]
        reduction_info["dropped"] = len(drop)

    elif reduction == FeatureReductionMethod.PCA:
        n_components = reduction_params.get("n_components", min(50, X.shape[1]))
        pca = PCA(n_components=n_components)
        X = pca.fit_transform(X)
        feature_names = [f"PC{i+1}" for i in range(X.shape[1])]
        reduction_info["explained_variance"] = pca.explained_variance_ratio_.tolist()

    elif reduction == FeatureReductionMethod.VARIANCE_THRESHOLD:
        threshold = reduction_params.get("threshold", 0.01)
        sel = VarianceThreshold(threshold=threshold)
        X = sel.fit_transform(X)
        mask = sel.get_support()
        feature_names = [feature_names[i] for i, m in enumerate(mask) if m]
        reduction_info["kept"] = int(mask.sum())

    elif reduction == FeatureReductionMethod.SELECT_K_BEST:
        k = reduction_params.get("k", min(50, X.shape[1]))
        # Need targets for this — use first target col
        meta = json.loads((DATA_DIR / dataset_id / "meta.json").read_text())
        if meta.get("target_cols"):
            tcol = meta["target_cols"][0]
            y = df.loc[valid_indices, tcol].values.astype(float)
            y = np.nan_to_num(y)
            sel = SelectKBest(f_regression, k=k)
            X = sel.fit_transform(X, y)
            mask = sel.get_support()
            feature_names = [feature_names[i] for i, m in enumerate(mask) if m]
            reduction_info["scores"] = sel.scores_[mask].tolist()

    # ── 4. Save feature set ───────────────────────────────
    fs_id = str(uuid.uuid4())[:8]
    save_dir = FEATURE_DIR / fs_id
    save_dir.mkdir(parents=True, exist_ok=True)

    np.save(save_dir / "X.npy", X)
    np.save(save_dir / "indices.npy", np.array(valid_indices))
    meta = {
        "id": fs_id,
        "dataset_id": dataset_id,
        "method": method.value,
        "reduction": reduction.value,
        "n_features": X.shape[1],
        "n_samples": X.shape[0],
        "n_raw_features": n_raw,
        "feature_names": feature_names[:100],  # cap for response
        "reduction_info": reduction_info,
        "stats": {
            "mean": float(X.mean()),
            "std": float(X.std()),
            "min": float(X.min()),
            "max": float(X.max()),
            "sparsity": float((X == 0).mean()),
        },
    }
    (save_dir / "meta.json").write_text(json.dumps(meta))
    return meta


def load_feature_set(fs_id: str) -> tuple[np.ndarray, np.ndarray, dict]:
    """Load features, valid indices, and metadata."""
    save_dir = FEATURE_DIR / fs_id
    X = np.load(save_dir / "X.npy")
    indices = np.load(save_dir / "indices.npy")
    meta = json.loads((save_dir / "meta.json").read_text())
    return X, indices, meta


def list_feature_sets() -> list[dict]:
    """Return metadata for all saved feature sets."""
    results = []
    if FEATURE_DIR.exists():
        for d in sorted(FEATURE_DIR.iterdir()):
            meta_file = d / "meta.json"
            if d.is_dir() and meta_file.exists():
                results.append(json.loads(meta_file.read_text()))
    return results


def get_feature_set_info(fs_id: str) -> dict:
    """Return metadata for a single feature set."""
    meta_file = FEATURE_DIR / fs_id / "meta.json"
    if not meta_file.exists():
        return {"error": f"Feature set {fs_id} not found"}
    return json.loads(meta_file.read_text())


def _compute_features(
    smiles_a: str, smiles_b: str, method: FeaturizationMethod
) -> np.ndarray | None:
    """Compute features for a single pair."""
    try:
        if method == FeaturizationMethod.MORGAN_FP:
            fp_a = smiles_to_morgan_fp(smiles_a)
            fp_b = smiles_to_morgan_fp(smiles_b)
            if fp_a is None or fp_b is None:
                return None
            return np.concatenate([fp_a, fp_b])  # 4096

        elif method == FeaturizationMethod.FLAT_GRAPH:
            return pair_flat_features(smiles_a, smiles_b)  # 248

        elif method == FeaturizationMethod.RDKIT_DESCRIPTORS:
            d_a = compute_rdkit_descriptors(smiles_a)
            d_b = compute_rdkit_descriptors(smiles_b)
            if d_a is None or d_b is None:
                return None
            return np.concatenate([d_a, d_b])

        elif method == FeaturizationMethod.AUTOCORR_3D:
            a3d_a = compute_3d_autocorr(smiles_a)
            a3d_b = compute_3d_autocorr(smiles_b)
            if a3d_a is None or a3d_b is None:
                return None
            return np.concatenate([a3d_a, a3d_b])  # 160

        elif method == FeaturizationMethod.COMBINED_2D_3D:
            fp_a = smiles_to_morgan_fp(smiles_a)
            fp_b = smiles_to_morgan_fp(smiles_b)
            a3d_a = compute_3d_autocorr(smiles_a)
            a3d_b = compute_3d_autocorr(smiles_b)
            if any(x is None for x in [fp_a, fp_b, a3d_a, a3d_b]):
                return None
            return np.concatenate([fp_a, a3d_a, fp_b, a3d_b])  # 2128×2

        elif method == FeaturizationMethod.GRAPH_FEATURES:
            return pair_flat_features(smiles_a, smiles_b)

        return None
    except Exception:
        return None


def get_feature_correlation(fs_id: str, max_features: int = 50) -> dict:
    """Compute correlation matrix for visualization."""
    X, _, meta = load_feature_set(fs_id)
    n = min(max_features, X.shape[1])
    X_sub = X[:, :n]
    corr = np.corrcoef(X_sub.T)
    corr = np.nan_to_num(corr)
    names = meta.get("feature_names", [f"f{i}" for i in range(n)])[:n]
    return {
        "matrix": corr.tolist(),
        "names": names,
    }
