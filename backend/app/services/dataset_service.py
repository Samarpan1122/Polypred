"""Dataset service - upload, store, preview, split CSV datasets."""

from __future__ import annotations

import os
import uuid
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split, KFold, StratifiedKFold

from app.models.schemas import SplitConfig, SplitMethod

DATA_DIR = Path(os.getenv("DATA_DIR", "/tmp/polypred_data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)


def save_dataset(filename: str, content: bytes) -> dict:
    """Save an uploaded CSV/XLSX and return metadata."""
    dataset_id = str(uuid.uuid4())[:8]
    save_dir = DATA_DIR / dataset_id
    save_dir.mkdir(parents=True, exist_ok=True)

    # Ensure filename is a string
    if isinstance(filename, bytes):
        filename = filename.decode("utf-8", errors="replace")

    filepath = save_dir / filename
    filepath.write_bytes(content)

    # Read CSV or Excel based on extension
    ext = filepath.suffix.lower()
    if ext in (".xlsx", ".xls"):
        df = pd.read_excel(filepath)
    else:
        df = pd.read_csv(filepath)

    # Auto-detect SMILES columns
    smiles_a = smiles_b = None
    for col in df.columns:
        cl = col.lower().replace(" ", "_")
        if "smiles" in cl:
            if any(x in cl for x in ("_a", "_1", "monomer_a", "monomera")):
                smiles_a = col
            elif any(x in cl for x in ("_b", "_2", "monomer_b", "monomerb")):
                smiles_b = col
    if not smiles_a:
        smiles_cols = [c for c in df.columns if "smiles" in c.lower()]
        if len(smiles_cols) >= 2:
            smiles_a, smiles_b = smiles_cols[0], smiles_cols[1]
        elif len(smiles_cols) == 1:
            smiles_a = smiles_cols[0]

    # Detect target columns
    targets = []
    for col in df.columns:
        cl = col.lower()
        if cl in ("r1", "r2", "r_1", "r_2", "log_r1", "log_r2", "reactivity_ratio_1", "reactivity_ratio_2"):
            targets.append(col)

    smiles_columns = [c for c in [smiles_a, smiles_b] if c]

    meta = {
        "id": dataset_id,
        "name": filename,
        "filename": filename,
        "rows": len(df),
        "cols": len(df.columns),
        "columns": list(df.columns),
        "smiles_columns": smiles_columns,
        "target_columns": targets,
        "uploaded_at": datetime.utcnow().isoformat(),
        "dtypes": {c: str(df[c].dtype) for c in df.columns},
        "preview": df.head(10).replace({np.nan: None}).to_dict(orient="records"),
    }
    (save_dir / "meta.json").write_text(json.dumps(meta))
    return meta


def get_dataset(dataset_id: str) -> dict:
    meta_path = DATA_DIR / dataset_id / "meta.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"Dataset {dataset_id} not found")
    return json.loads(meta_path.read_text())


def load_dataframe(dataset_id: str) -> pd.DataFrame:
    meta = get_dataset(dataset_id)
    csv_path = DATA_DIR / dataset_id / meta["filename"]
    return pd.read_csv(csv_path)


def list_datasets() -> list[dict]:
    results = []
    if not DATA_DIR.exists():
        return results
    for d in sorted(DATA_DIR.iterdir()):
        mp = d / "meta.json"
        if mp.exists():
            meta = json.loads(mp.read_text())
            results.append({
                "id": meta["id"],
                "name": meta.get("name", meta.get("filename", "dataset")),
                "rows": meta["rows"],
                "cols": meta.get("cols", len(meta.get("columns", []))),
                "columns": meta.get("columns", []),
                "smiles_columns": meta.get("smiles_columns", []),
                "target_columns": meta.get("target_columns", meta.get("target_cols", [])),
                "uploaded_at": meta.get("uploaded_at", ""),
            })
    return results


def delete_dataset(dataset_id: str):
    import shutil
    p = DATA_DIR / dataset_id
    if p.exists():
        shutil.rmtree(p)


def get_dataset_stats(dataset_id: str) -> dict:
    df = load_dataframe(dataset_id)
    stats = {}
    for col in df.select_dtypes(include=[np.number]).columns:
        col_series = df[col]
        stats[col] = {
            "mean": round(float(col_series.mean()), 4) if not pd.isna(col_series.mean()) else None,
            "std": round(float(col_series.std()), 4) if not pd.isna(col_series.std()) else None,
            "min": round(float(col_series.min()), 4) if not pd.isna(col_series.min()) else None,
            "max": round(float(col_series.max()), 4) if not pd.isna(col_series.max()) else None,
            "median": round(float(col_series.median()), 4) if not pd.isna(col_series.median()) else None,
            "missing": int(col_series.isna().sum()),
        }
    return stats


def split_dataset(
    dataset_id: str,
    config: SplitConfig,
) -> dict:
    """Split dataset and return indices for train/val/test."""
    df = load_dataframe(dataset_id)
    n = len(df)
    indices = np.arange(n)

    if config.method == SplitMethod.RANDOM:
        train_val_idx, test_idx = train_test_split(
            indices, test_size=config.test_size, random_state=config.random_seed
        )
        if config.val_size > 0:
            val_frac = config.val_size / (1 - config.test_size)
            train_idx, val_idx = train_test_split(
                train_val_idx, test_size=val_frac, random_state=config.random_seed
            )
        else:
            train_idx, val_idx = train_val_idx, np.array([], dtype=int)

        return {
            "method": "random",
            "train_size": len(train_idx),
            "val_size": len(val_idx),
            "test_size": len(test_idx),
            "train_idx": train_idx.tolist(),
            "val_idx": val_idx.tolist(),
            "test_idx": test_idx.tolist(),
        }

    elif config.method == SplitMethod.KFOLD:
        kf = KFold(n_splits=config.n_folds, shuffle=True, random_state=config.random_seed)
        folds = []
        for fold_i, (train_idx, test_idx) in enumerate(kf.split(indices)):
            folds.append({
                "fold": fold_i,
                "train_idx": train_idx.tolist(),
                "test_idx": test_idx.tolist(),
            })
        return {
            "method": "kfold",
            "n_folds": config.n_folds,
            "folds": folds,
        }

    return {"method": config.method, "error": "Not yet implemented"}
