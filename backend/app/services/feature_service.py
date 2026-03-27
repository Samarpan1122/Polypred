"""Feature engineering service - featurize datasets, apply reductions."""

from __future__ import annotations

import os
import uuid
import json
import pickle
from pathlib import Path
from typing import Any
from collections.abc import Callable

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
from app.services.dataset_service import load_dataframe, get_dataset

FEATURE_DIR = Path(os.getenv("FEATURE_DIR", "/tmp/polypred_features"))
FEATURE_DIR.mkdir(parents=True, exist_ok=True)


def featurize_dataset(
    dataset_id: str,
    smiles_col_a: str,
    smiles_col_b: str,
    methods: list[FeaturizationMethod],
    reduction: FeatureReductionMethod = FeatureReductionMethod.NONE,
    reduction_params: dict[str, Any] | None = None,
    owner_id: str | None = None,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> dict:
    """Featurize every row of a dataset and optionally reduce features."""
    df = load_dataframe(dataset_id, owner_id=owner_id)
    reduction_params = reduction_params or {}

    # ── 1. Generate raw features ──────────────────────────
    features = []
    valid_indices = []
    feature_names: list[str] = []

    real_methods = []
    for m in methods:
        if m == FeaturizationMethod.ALL:
            real_methods = [x for x in FeaturizationMethod if x != FeaturizationMethod.ALL]
            break
        elif m not in real_methods:
            real_methods.append(m)

    total_rows = len(df)
    for row_num, (i, row) in enumerate(df.iterrows()):
        if row_num % 50 == 0:
            print(f"[FEATURIZE] Processing row {row_num+1}/{total_rows} ({100*row_num/max(total_rows,1):.0f}%)", flush=True)
            if progress_callback is not None:
                progress_callback(row_num + 1, total_rows, "featurizing")
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

    print(f"[FEATURIZE] Done - {len(features)} valid out of {total_rows} rows", flush=True)
    if progress_callback is not None:
        progress_callback(total_rows, total_rows, "featurizing_done")

    if not features:
        return {"error": "No valid features could be computed"}

    X = np.array(features, dtype=np.float32)
    n_samples, n_raw = X.shape

    # Generate feature names
    if any(m == FeaturizationMethod.ALL for m in methods):
        feature_names = [f"feat_{i}" for i in range(n_raw)]
    else:
        from app.models.feature_engineering import _BASE_65_NAMES, _BIG8_FEATURE_MAP
        feature_names = []
        for m in real_methods:
            keywords = _BIG8_FEATURE_MAP.get(m.value, [])
            mask = []
            for _ in range(2):
                for name in _BASE_65_NAMES:
                    mask.append(any(kw in name for kw in keywords))
            base_names = [(f"{name}_A" if j == 0 else f"{name}_B") for j in range(2) for name in _BASE_65_NAMES]
            m_names = [fn for fn, mk in zip(base_names, mask) if mk]
            feature_names.extend(m_names)
        
        if not feature_names:
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
        # Need targets for this - use first target col
        meta = get_dataset(dataset_id, owner_id=owner_id)
        target_cols = meta.get("target_columns") or meta.get("target_cols") or []
        if target_cols:
            tcol = target_cols[0]
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
        "method": "+".join(m.value for m in real_methods),
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
        from app.models.feature_engineering import pair_flat_features_ensemble_masked
        return pair_flat_features_ensemble_masked(smiles_a, smiles_b, method.value)
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
