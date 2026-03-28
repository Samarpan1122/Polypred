"""Dataset service - upload, store, preview, split CSV datasets."""

from __future__ import annotations

import os
import uuid
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split, KFold, StratifiedKFold

from app.models.schemas import SplitConfig, SplitMethod
from app.services import s3_service

DATA_DIR = Path(os.getenv("DATA_DIR", "/tmp/polypred_data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _owner_slug(owner_id: str | None) -> str:
    raw = (owner_id or "anonymous").strip().lower()
    safe = re.sub(r"[^a-z0-9._-]", "-", raw)
    safe = re.sub(r"-+", "-", safe).strip("-.")
    return safe or "anonymous"


def _owner_dir(owner_id: str | None) -> Path:
    p = DATA_DIR / "users" / _owner_slug(owner_id)
    p.mkdir(parents=True, exist_ok=True)
    return p


def resolve_dataset_owner(dataset_id: str) -> str | None:
    users_root = DATA_DIR / "users"
    if not users_root.exists():
        return None
    for owner_dir in users_root.iterdir():
        if (owner_dir / dataset_id / "meta.json").exists():
            return owner_dir.name
    return None


def _guess_content_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".csv":
        return "text/csv"
    if ext in (".xlsx", ".xls"):
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return "application/octet-stream"


def _update_meta(owner: str, dataset_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    meta_path = _owner_dir(owner) / dataset_id / "meta.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"Missing metadata for dataset {dataset_id}")
    meta = json.loads(meta_path.read_text())
    meta.update(updates)
    meta_path.write_text(json.dumps(meta))
    return meta


def save_dataset(
    filename: str,
    content: bytes,
    owner_id: str | None = None,
    sync_to_s3: bool = True,
) -> dict:
    """Save an uploaded CSV/XLSX and return metadata."""
    dataset_id = str(uuid.uuid4())[:8]
    owner = _owner_slug(owner_id)
    save_dir = _owner_dir(owner) / dataset_id
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
        row_count = int(len(df))
        preview_df = df.head(10)
    else:
        # Avoid full parse in request path for large CSV uploads.
        df = pd.read_csv(filepath, nrows=2000)
        row_count = max(content.count(b"\n") - 1, 0)
        preview_df = df.head(10)

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
        "owner_id": owner,
        "name": filename,
        "filename": filename,
        "rows": row_count,
        "cols": len(df.columns),
        "columns": list(df.columns),
        "smiles_columns": smiles_columns,
        "target_columns": targets,
        "uploaded_at": datetime.utcnow().isoformat(),
        "dtypes": {c: str(df[c].dtype) for c in df.columns},
        "preview": preview_df.replace({np.nan: None}).to_dict(orient="records"),
        "s3_synced": False,
        "s3_sync_status": "pending" if sync_to_s3 else "queued",
        "is_public": False,
        "public_share_status": "private",
    }

    meta_path = save_dir / "meta.json"
    meta_path.write_text(json.dumps(meta))

    if sync_to_s3:
        # Best-effort S3 mirror for persistent multi-user storage.
        try:
            prefixes = s3_service.ensure_user_prefixes(owner)
            file_key = f"{prefixes['datasets']}{dataset_id}/{filename}"
            meta_key = f"{prefixes['datasets']}{dataset_id}/meta.json"
            s3_service.upload_bytes(content, file_key, content_type=_guess_content_type(filename))
            s3_service.upload_json(meta, meta_key)
            meta["s3_key"] = file_key
            meta["s3_meta_key"] = meta_key
            meta["s3_synced"] = True
            meta["s3_sync_status"] = "completed"
            meta_path.write_text(json.dumps(meta))
        except Exception as exc:
            # Keep local storage available even if S3 is temporarily unavailable.
            meta["s3_error"] = str(exc)
            meta["s3_sync_status"] = "failed"
            meta_path.write_text(json.dumps(meta))

    return meta


def sync_dataset_to_s3(dataset_id: str, owner_id: str | None = None) -> dict[str, Any]:
    owner = _owner_slug(owner_id)
    ds_dir = _owner_dir(owner) / dataset_id
    meta_path = ds_dir / "meta.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"Dataset {dataset_id} metadata not found")

    meta = json.loads(meta_path.read_text())
    filename = meta.get("filename")
    if not filename:
        raise ValueError(f"Dataset {dataset_id} has no filename")

    data_path = ds_dir / filename
    if not data_path.exists():
        raise FileNotFoundError(f"Dataset file missing: {data_path}")

    try:
        _update_meta(owner, dataset_id, {"s3_sync_status": "syncing"})
        prefixes = s3_service.ensure_user_prefixes(owner)
        file_key = f"{prefixes['datasets']}{dataset_id}/{filename}"
        meta_key = f"{prefixes['datasets']}{dataset_id}/meta.json"
        s3_service.upload_bytes(
            data_path.read_bytes(),
            file_key,
            content_type=_guess_content_type(filename),
        )
        synced_meta = _update_meta(
            owner,
            dataset_id,
            {
                "s3_synced": True,
                "s3_sync_status": "completed",
                "s3_key": file_key,
                "s3_meta_key": meta_key,
                "s3_error": None,
            },
        )
        s3_service.upload_json(synced_meta, meta_key)
        return synced_meta
    except Exception as exc:
        return _update_meta(
            owner,
            dataset_id,
            {
                "s3_synced": False,
                "s3_sync_status": "failed",
                "s3_error": str(exc),
            },
        )


def get_dataset(dataset_id: str, owner_id: str | None = None) -> dict:
    owner = _owner_slug(owner_id)
    meta_path = _owner_dir(owner) / dataset_id / "meta.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"Dataset {dataset_id} not found for owner {owner}")
    return json.loads(meta_path.read_text())


def load_dataframe(dataset_id: str, owner_id: str | None = None) -> pd.DataFrame:
    meta = get_dataset(dataset_id, owner_id=owner_id)
    owner = _owner_slug(meta.get("owner_id") or owner_id)
    csv_path = _owner_dir(owner) / dataset_id / meta["filename"]
    if not csv_path.exists() and meta.get("s3_key"):
        try:
            s3_service.download_file(meta["s3_key"], csv_path)
        except Exception as exc:
            raise FileNotFoundError(f"Dataset file missing locally and S3 restore failed: {exc}")
    ext = csv_path.suffix.lower()
    if ext in (".xlsx", ".xls"):
        return pd.read_excel(csv_path)
    return pd.read_csv(csv_path)


def list_datasets(owner_id: str | None = None) -> list[dict]:
    results = []
    base = _owner_dir(owner_id)
    if not base.exists():
        return results
    for d in sorted(base.iterdir()):
        mp = d / "meta.json"
        if mp.exists():
            meta = json.loads(mp.read_text())
            results.append({
                "id": meta["id"],
                "name": meta.get("name", meta.get("filename", "dataset")),
                "filename": meta.get("filename", meta.get("name", "dataset")),
                "owner_id": meta.get("owner_id", owner_id),
                "rows": meta["rows"],
                "cols": meta.get("cols", len(meta.get("columns", []))),
                "columns": meta.get("columns", []),
                "smiles_columns": meta.get("smiles_columns", []),
                "target_columns": meta.get("target_columns", meta.get("target_cols", [])),
                "uploaded_at": meta.get("uploaded_at", ""),
                "s3_synced": bool(meta.get("s3_synced", False)),
                "s3_key": meta.get("s3_key"),
                "s3_sync_status": meta.get("s3_sync_status", "unknown"),
                "is_public": bool(meta.get("is_public", False)),
                "public_share_status": meta.get("public_share_status", "private"),
            })
    return results


def delete_dataset(dataset_id: str, owner_id: str | None = None):
    import shutil
    owner = _owner_slug(owner_id)
    p = _owner_dir(owner) / dataset_id
    if p.exists():
        shutil.rmtree(p)
        try:
            s3_service.delete_prefix(f"users/{owner}/datasets/{dataset_id}/")
        except Exception:
            pass
        return True
    return False


def get_dataset_stats(dataset_id: str, owner_id: str | None = None) -> dict:
    df = load_dataframe(dataset_id, owner_id=owner_id)
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
    owner_id: str | None = None,
) -> dict:
    """Split dataset and return indices for train/val/test."""
    df = load_dataframe(dataset_id, owner_id=owner_id)
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
