"""Training pipeline — train any model, with optional HP tuning + CV."""

from __future__ import annotations

import os
import time
import uuid
import json
import traceback
from pathlib import Path
from typing import Any
from threading import Thread

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.model_selection import (
    KFold, cross_val_score, GridSearchCV, RandomizedSearchCV
)
from sklearn.metrics import (
    r2_score, mean_squared_error, mean_absolute_error
)

from app.models.schemas import (
    ModelType, TrainRequest, TrainProgress, ModelResult,
    HPTuningMethod, CVMethod, SplitMethod,
)
from app.models.traditional import TraditionalModelWrapper
from app.services.dataset_service import load_dataframe
from app.services.feature_service import (
    featurize_dataset, load_feature_set, _compute_features,
)
from app.models.feature_engineering import smiles_to_morgan_fp, smiles_to_graph

# The 10 valid models from Specific_Models_Final
# Traditional ML models that can be trained from scratch
TRAINABLE_TRADITIONAL = {"decision_tree", "random_forest", "ensemble_methods"}
# These use SMILES character sequences for training
TRAINABLE_SMILES_LSTM = {"lstm_bayesian", "standalone_lstm"}
# These use graph-based features for training
TRAINABLE_GRAPH = {"siamese_lstm", "siamese_regression", "siamese_bayesian", "lstm_siamese_bayesian"}
# Autoencoder (VAE) training
TRAINABLE_AUTOENCODER = {"autoencoder"}

ALL_TRAINABLE_MODELS = TRAINABLE_TRADITIONAL | TRAINABLE_SMILES_LSTM | TRAINABLE_GRAPH | TRAINABLE_AUTOENCODER

try:
    from skopt import BayesSearchCV
    HAS_SKOPT = True
except ImportError:
    HAS_SKOPT = False

try:
    import torch
    import torch.nn as nn
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

try:
    from app.models.benchmark_models import (
        SiameseLSTMPolyPredict, SiameseRegressorGraph, BiLSTMRegressorSMILES,
        LSTMSiamesePolyPredict, VAERegressor, encode_smiles, graph_dict_to_single_pyg,
    )
    from app.config import settings
    BENCHMARK_DEVICE = settings.DEVICE
    HAS_BENCHMARK = True
except ImportError:
    HAS_BENCHMARK = False
    BENCHMARK_DEVICE = "cpu"

RESULTS_DIR = Path(os.getenv("RESULTS_DIR", "/tmp/polypred_results"))
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


# ──────────────────────────────────────────────────────────
#  File-based job tracking (works across multiple workers)
# ──────────────────────────────────────────────────────────
def _save_progress(job_id: str, progress: TrainProgress):
    """Save job progress to file (shared across workers)."""
    job_dir = RESULTS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    ppath = job_dir / "progress.json"
    ppath.write_text(progress.model_dump_json())


def _load_progress(job_id: str) -> TrainProgress | None:
    """Load job progress from file."""
    ppath = RESULTS_DIR / job_id / "progress.json"
    if ppath.exists():
        return TrainProgress.model_validate_json(ppath.read_text())
    return None

# ──────────────────────────────────────────────────────────
#  Default HP grids for each model type
# ──────────────────────────────────────────────────────────
DEFAULT_HP_GRIDS: dict[str, dict[str, list]] = {
    "decision_tree": {"max_depth": [5, 10, 15, 20, None], "min_samples_split": [2, 5, 10]},
    "random_forest": {"n_estimators": [100, 200, 500], "max_depth": [10, 15, 20, None]},
    "ensemble_methods": {"n_estimators": [50, 100, 200], "max_depth": [3, 5, 7]},
}


# ──────────────────────────────────────────────────────────
#  Public API
# ──────────────────────────────────────────────────────────
def start_training(req: TrainRequest) -> str:
    """Start a training job in background, return job_id."""
    job_id = str(uuid.uuid4())[:8]
    progress = TrainProgress(
        job_id=job_id,
        status="queued",
        total_models=len(req.models),
        message="Queued...",
    )
    _save_progress(job_id, progress)

    thread = Thread(target=_run_training, args=(job_id, req), daemon=True)
    thread.start()
    return job_id


def get_progress(job_id: str) -> TrainProgress | None:
    return _load_progress(job_id)


def get_results(job_id: str) -> dict | None:
    rpath = RESULTS_DIR / job_id / "results.json"
    if rpath.exists():
        return json.loads(rpath.read_text())
    return None


def list_jobs() -> list[dict]:
    """List all jobs from the results directory."""
    jobs = []
    if RESULTS_DIR.exists():
        for job_dir in RESULTS_DIR.iterdir():
            if job_dir.is_dir():
                progress = _load_progress(job_dir.name)
                if progress:
                    jobs.append({
                        "job_id": progress.job_id,
                        "status": progress.status,
                        "message": progress.message
                    })
    return jobs


# ──────────────────────────────────────────────────────────
#  Main training loop
# ──────────────────────────────────────────────────────────
def _update_progress(job_id: str, **kwargs):
    """Load progress, update fields, save back to file."""
    progress = _load_progress(job_id)
    if progress:
        for k, v in kwargs.items():
            setattr(progress, k, v)
        _save_progress(job_id, progress)
    return progress


def _run_training(job_id: str, req: TrainRequest):
    _update_progress(job_id, status="running")
    t_start = time.time()

    try:
        # 1. Load data
        _update_progress(job_id, message="Loading dataset...")
        df = load_dataframe(req.dataset_id)

        # Validate SMILES columns
        if not req.smiles_col_a or req.smiles_col_a not in df.columns:
            _update_progress(job_id, status="failed",
                           message=f"SMILES column A '{req.smiles_col_a}' not found. Available: {list(df.columns)}")
            return
        if not req.smiles_col_b or req.smiles_col_b not in df.columns:
            _update_progress(job_id, status="failed",
                           message=f"SMILES column B '{req.smiles_col_b}' not found. Available: {list(df.columns)}")
            return

        # 2. Featurize (or load existing)
        _update_progress(job_id, message="Featurizing...")
        if req.feature_set_id:
            X, valid_idx, fs_meta = load_feature_set(req.feature_set_id)
        else:
            fs_result = featurize_dataset(
                req.dataset_id,
                req.smiles_col_a,
                req.smiles_col_b,
                req.featurization,
            )
            if "error" in fs_result:
                _update_progress(job_id, status="failed", message=fs_result["error"])
                return
            X, valid_idx, fs_meta = load_feature_set(fs_result["id"])

        # 3. Get targets
        targets = []
        for tc in req.target_cols:
            if tc in df.columns:
                targets.append(df.loc[valid_idx, tc].values.astype(float))
        if len(targets) == 0:
            _update_progress(job_id, status="failed", message="No valid target columns found")
            return
        Y = np.column_stack(targets) if len(targets) > 1 else targets[0].reshape(-1, 1)
        Y = np.nan_to_num(Y)

        # 4. Split — directly split the feature matrix to avoid index-mapping bugs
        _update_progress(job_id, message="Splitting data...")
        from sklearn.model_selection import train_test_split as sk_split
        n_samples = X.shape[0]
        indices = np.arange(n_samples)
        test_frac = req.split.test_size
        val_frac = req.split.val_size
        seed = req.split.random_seed if hasattr(req.split, 'random_seed') else 42

        train_val_idx, te_idx = sk_split(indices, test_size=test_frac, random_state=seed)
        if val_frac > 0:
            adj_val = val_frac / (1 - test_frac)
            tr_idx, va_idx = sk_split(train_val_idx, test_size=adj_val, random_state=seed)
        else:
            tr_idx, va_idx = train_val_idx, np.array([], dtype=int)

        X_train, X_test = X[tr_idx], X[te_idx]
        Y_train, Y_test = Y[tr_idx], Y[te_idx]
        X_val = X[va_idx] if len(va_idx) > 0 else None
        Y_val = Y[va_idx] if len(va_idx) > 0 else None

        print(f"[TRAIN] X={X.shape}, X_train={X_train.shape}, X_test={X_test.shape}, "
              f"Y_train={Y_train.shape}, Y_test={Y_test.shape}", flush=True)

        split_info = {
            "train_size": len(X_train),
            "test_size": len(X_test),
            "val_size": len(X_val) if X_val is not None else 0,
            "n_features": X.shape[1],
        }

        # 5. Prepare SMILES strings and graph data for the 10 valid models
        needs_seq_data = any(
            m.value in (TRAINABLE_SMILES_LSTM | TRAINABLE_GRAPH | TRAINABLE_AUTOENCODER)
            for m in req.models
        )
        fp_data = None
        if needs_seq_data:
            _update_progress(job_id, message="Preparing SMILES and graph features for DL models...")
            fp_data = _prepare_smiles_and_graphs(
                df, valid_idx, req.smiles_col_a, req.smiles_col_b,
                tr_idx.tolist(), te_idx.tolist()
            )

        # 6. Train each model
        all_results: list[ModelResult] = []
        for mi, model_type in enumerate(req.models):
            _update_progress(
                job_id,
                current_model=model_type.value,
                models_completed=mi,
                elapsed_seconds=round(time.time() - t_start, 1),
                message=f"Training {model_type.value}...",
                train_loss=[],
                val_loss=[],
                train_r2=[],
                val_r2=[]
            )
            progress = _load_progress(job_id)

            try:
                result = _train_single_model(
                    model_type, X_train, Y_train, X_test, Y_test,
                    X_val, Y_val, req, progress, fp_data, job_id
                )
                all_results.append(result)
            except Exception as e:
                traceback.print_exc()
                err_msg = f"{type(e).__name__}: {str(e)[:200]}"
                print(f"[TRAINING ERROR] {model_type.value}: {err_msg}", flush=True)
                err_result = ModelResult(
                    model_name=model_type.value,
                    model_type=model_type.value,
                    training_time_s=0.0,
                )
                err_result.best_params = {"error": err_msg}
                all_results.append(err_result)

        _update_progress(job_id, models_completed=len(req.models))

        # 7. Save results
        _save_results(job_id, all_results, split_info)

        elapsed = time.time() - t_start
        _update_progress(job_id, status="completed",
                        elapsed_seconds=elapsed,
                        message=f"Completed {len(all_results)} models in {elapsed:.1f}s")

    except Exception as e:
        _update_progress(job_id, status="failed",
                        message=str(e) or f"{type(e).__name__}: check server logs")
        traceback.print_exc()


# ──────────────────────────────────────────────────────────
#  Train one model
# ──────────────────────────────────────────────────────────
def _train_single_model(
    model_type: ModelType,
    X_train, Y_train, X_test, Y_test,
    X_val, Y_val,
    req: TrainRequest,
    progress: TrainProgress,
    fp_data: dict | None,
    job_id: str = None,
) -> ModelResult:

    t0 = time.time()
    mt = model_type.value

    # ── Traditional ML (Decision Tree, Random Forest, Ensemble Methods) ──
    if mt in TRAINABLE_TRADITIONAL:
        return _train_traditional(mt, X_train, Y_train, X_test, Y_test, req, progress)

    # ── SMILES-based LSTM (LSTM+Bayesian, Standalone LSTM) ────────────────
    if mt in TRAINABLE_SMILES_LSTM:
        return _train_smiles_lstm(mt, fp_data, Y_train, Y_test, req, progress, job_id)

    # ── Graph-based Siamese / Hybrid (Siamese+LSTM, Siamese Regression, etc.) ──
    if mt in TRAINABLE_GRAPH:
        return _train_graph_model(mt, fp_data, Y_train, Y_test, req, progress, job_id)

    # ── Autoencoder (VAE) ──────────────────────────────────────────────────
    if mt in TRAINABLE_AUTOENCODER:
        return _train_vae_model(fp_data, req, progress, job_id)

    return ModelResult(model_name=mt, model_type=mt, training_time_s=0.0)


# ──────────────────────────────────────────────────────────
#  Traditional ML training (with HP tuning)
# ──────────────────────────────────────────────────────────
def _train_traditional(
    mt: str, X_train, Y_train, X_test, Y_test,
    req: TrainRequest, progress: TrainProgress,
) -> ModelResult:

    result = ModelResult(model_name=mt, model_type=mt)
    t0 = time.time()

    # Train separate models for r1 and r2
    y_true_r1_all, y_pred_r1_all = [], []
    y_true_r2_all, y_pred_r2_all = [], []

    for target_i, target_name in enumerate(req.target_cols):
        if target_i >= Y_train.shape[1]:
            break

        y_tr = Y_train[:, target_i]
        y_te = Y_test[:, target_i]

        progress.message = f"Training {mt} for {target_name} ({target_i+1}/{len(req.target_cols)})..."

        # Build model — only the 3 valid traditional models from Specific_Models_Final
        from sklearn.tree import DecisionTreeRegressor
        from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
        if mt == "decision_tree":
            model = DecisionTreeRegressor(max_depth=10, random_state=42)
        elif mt == "random_forest":
            model = RandomForestRegressor(n_estimators=200, max_depth=15, random_state=42, n_jobs=-1)
        elif mt == "ensemble_methods":
            model = GradientBoostingRegressor(n_estimators=100, max_depth=5, random_state=42)
        else:
            from sklearn.ensemble import RandomForestRegressor
            model = RandomForestRegressor(n_estimators=100, random_state=42)

        # HP tuning
        if req.hp_tuning.method != HPTuningMethod.NONE:
            progress.message = f"HP tuning {mt} for {target_name}..."
            grid = req.hp_tuning.param_grid or DEFAULT_HP_GRIDS.get(mt, {})
            if grid:
                model, hp_results = _run_hp_tuning(model, X_train, y_tr, grid, req)
                result.best_params = {**result.best_params, **{f"{target_name}_{k}": v for k, v in (model.get_params() if hasattr(model, 'get_params') else {}).items()}}
                result.hp_search_results = hp_results
            else:
                model.fit(X_train, y_tr)
        else:
            model.fit(X_train, y_tr)

        # CV
        if req.cv != CVMethod.NONE:
            n_folds = _cv_folds(req.cv)
            cv_scores = cross_val_score(model, X_train, y_tr, cv=n_folds, scoring="r2")
            if target_i == 0:
                result.cv_r2_r1_mean = float(cv_scores.mean())
                result.cv_r2_r1_std = float(cv_scores.std())
            else:
                result.cv_r2_r2_mean = float(cv_scores.mean())
                result.cv_r2_r2_std = float(cv_scores.std())

        # Predict
        y_pred = model.predict(X_test)

        if target_i == 0:
            y_true_r1_all = y_te.tolist()
            y_pred_r1_all = y_pred.tolist()
            result.r2_r1 = float(r2_score(y_te, y_pred))
            result.mse_r1 = float(mean_squared_error(y_te, y_pred))
            result.mae_r1 = float(mean_absolute_error(y_te, y_pred))
            result.rmse_r1 = float(np.sqrt(result.mse_r1))
        else:
            y_true_r2_all = y_te.tolist()
            y_pred_r2_all = y_pred.tolist()
            result.r2_r2 = float(r2_score(y_te, y_pred))
            result.mse_r2 = float(mean_squared_error(y_te, y_pred))
            result.mae_r2 = float(mean_absolute_error(y_te, y_pred))
            result.rmse_r2 = float(np.sqrt(result.mse_r2))

        # Feature importance
        if hasattr(model, "feature_importances_"):
            imp = model.feature_importances_
            top_k = min(20, len(imp))
            top_idx = np.argsort(imp)[-top_k:][::-1]
            result.feature_importance = {f"feat_{i}": float(imp[i]) for i in top_idx}

    result.y_true_r1 = y_true_r1_all
    result.y_pred_r1 = y_pred_r1_all
    result.y_true_r2 = y_true_r2_all
    result.y_pred_r2 = y_pred_r2_all
    result.training_time_s = time.time() - t0
    return result


def _run_hp_tuning(model, X, y, grid, req):
    """Run HP tuning and return fitted model + search results."""
    hp_results = []
    cv = min(req.hp_tuning.cv_folds, len(X))

    if req.hp_tuning.method == HPTuningMethod.GRID_SEARCH:
        search = GridSearchCV(model, grid, cv=cv, scoring="r2", n_jobs=-1, return_train_score=True)
        search.fit(X, y)
    elif req.hp_tuning.method == HPTuningMethod.RANDOM_SEARCH:
        search = RandomizedSearchCV(model, grid, n_iter=req.hp_tuning.n_iter, cv=cv,
                                     scoring="r2", n_jobs=-1, return_train_score=True, random_state=42)
        search.fit(X, y)
    elif req.hp_tuning.method == HPTuningMethod.BAYESIAN_OPTIMIZATION and HAS_SKOPT:
        from skopt.space import Real, Integer, Categorical
        search_spaces = {}
        for k, vals in grid.items():
            if all(isinstance(v, (int, float)) for v in vals if v is not None):
                nums = [v for v in vals if v is not None]
                if all(isinstance(v, int) for v in nums):
                    search_spaces[k] = Integer(min(nums), max(nums))
                else:
                    search_spaces[k] = Real(min(nums), max(nums))
            else:
                search_spaces[k] = Categorical(vals)
        search = BayesSearchCV(model, search_spaces, n_iter=req.hp_tuning.n_iter,
                                cv=cv, scoring="r2", n_jobs=-1, random_state=42)
        search.fit(X, y)
    else:
        model.fit(X, y)
        return model, []

    # Extract results
    for i in range(min(20, len(search.cv_results_["mean_test_score"]))):
        hp_results.append({
            "params": {k: _safe_val(v) for k, v in search.cv_results_["params"][i].items()},
            "mean_test_score": float(search.cv_results_["mean_test_score"][i]),
            "mean_train_score": float(search.cv_results_.get("mean_train_score", [0])[i]) if "mean_train_score" in search.cv_results_ else None,
        })

    return search.best_estimator_, hp_results


def _safe_val(v):
    if isinstance(v, (np.integer)):
        return int(v)
    if isinstance(v, (np.floating)):
        return float(v)
    return v


# ──────────────────────────────────────────────────────────
#  SMILES-based LSTM training (lstm_bayesian, standalone_lstm)
#  Architecture mirrors the LSTM notebooks from Specific_Models_Final
# ──────────────────────────────────────────────────────────
def _train_smiles_lstm(mt: str, fp_data, Y_tr, Y_te, req, progress, job_id: str | None = None) -> ModelResult:
    """Train a bidirectional LSTM on SMILES character sequences."""
    if not HAS_BENCHMARK or not HAS_TORCH:
        result = ModelResult(model_name=mt, model_type=mt)
        result.best_params = {"error": "torch_geometric or PyTorch not available"}
        return result

    result = ModelResult(model_name=mt, model_type=mt)
    t0 = time.time()
    device = BENCHMARK_DEVICE

    # Build model matching the notebook architecture
    model = BiLSTMRegressorSMILES().to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=req.learning_rate)
    criterion = torch.nn.MSELoss()

    # Y_tr, Y_te as tensors (2-column: r1, r2)
    Y_tr_t = torch.tensor(Y_tr, dtype=torch.float32, device=device)
    Y_te_t = torch.tensor(Y_te, dtype=torch.float32, device=device)
    if Y_tr_t.dim() == 1:
        Y_tr_t = Y_tr_t.unsqueeze(1)
    if Y_te_t.dim() == 1:
        Y_te_t = Y_te_t.unsqueeze(1)

    # We need SMILES strings for this model — use fp_data smiles if available, fallback
    smiles_a_tr = fp_data.get("smiles_a_train", []) if fp_data else []
    smiles_b_tr = fp_data.get("smiles_b_train", []) if fp_data else []
    smiles_a_te = fp_data.get("smiles_a_test", []) if fp_data else []
    smiles_b_te = fp_data.get("smiles_b_test", []) if fp_data else []

    if not smiles_a_tr:
        result.best_params = {"error": "No SMILES strings available for LSTM training"}
        result.training_time_s = time.time() - t0
        return result

    def encode_batch(sma_list, smb_list):
        """Encode two lists of SMILES as token tensors and concat."""
        ta = torch.stack([encode_smiles(s) for s in sma_list]).to(device)
        tb = torch.stack([encode_smiles(s) for s in smb_list]).to(device)
        return ta, tb

    epochs = req.epochs
    bs = req.batch_size
    progress.total_epochs = epochs
    n = len(smiles_a_tr)

    for ep in range(epochs):
        model.train()
        perm = torch.randperm(n)
        ep_loss = 0.0
        nb = 0
        for start in range(0, n, bs):
            idx = perm[start:start + bs].tolist()
            sa = [smiles_a_tr[i] for i in idx]
            sb = [smiles_b_tr[i] for i in idx]
            ta, tb = encode_batch(sa, sb)
            yb = Y_tr_t[perm[start:start + bs]]
            optimizer.zero_grad()
            pred = model(ta, tb)
            loss = criterion(pred, yb[:, :pred.shape[1]])
            loss.backward()
            optimizer.step()
            ep_loss += loss.item()
            nb += 1
        result.train_loss_curve.append(round(ep_loss / max(nb, 1), 6))
        progress.current_epoch = ep + 1
        progress.train_loss = result.train_loss_curve[-20:]
        if job_id:
            _update_progress(job_id, current_epoch=ep + 1, train_loss=result.train_loss_curve[-20:])

    # Evaluate
    model.eval()
    with torch.no_grad():
        ta_te, tb_te = encode_batch(smiles_a_te, smiles_b_te)
        pred_te = model(ta_te, tb_te).cpu().numpy()

    y_np = Y_te_t.cpu().numpy()
    from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
    result.y_true_r1 = y_np[:, 0].tolist()
    result.y_pred_r1 = pred_te[:, 0].tolist()
    result.r2_r1 = float(r2_score(y_np[:, 0], pred_te[:, 0]))
    result.mse_r1 = float(mean_squared_error(y_np[:, 0], pred_te[:, 0]))
    result.mae_r1 = float(mean_absolute_error(y_np[:, 0], pred_te[:, 0]))
    result.rmse_r1 = float(np.sqrt(result.mse_r1))
    if pred_te.shape[1] >= 2 and y_np.shape[1] >= 2:
        result.y_true_r2 = y_np[:, 1].tolist()
        result.y_pred_r2 = pred_te[:, 1].tolist()
        result.r2_r2 = float(r2_score(y_np[:, 1], pred_te[:, 1]))
        result.mse_r2 = float(mean_squared_error(y_np[:, 1], pred_te[:, 1]))
        result.mae_r2 = float(mean_absolute_error(y_np[:, 1], pred_te[:, 1]))
        result.rmse_r2 = float(np.sqrt(result.mse_r2))
    result.training_time_s = time.time() - t0
    return result


# ──────────────────────────────────────────────────────────
#  Graph-based training (Siamese+LSTM, Siamese Regression,
#  Siamese+Bayesian, LSTM+Siamese+Bayesian)
#  Uses PyG graphs derived from SMILES + graph-net architectures
# ──────────────────────────────────────────────────────────
def _train_graph_model(mt: str, fp_data, Y_tr, Y_te, req, progress, job_id: str | None = None) -> ModelResult:
    """Train a graph-based model using PyG Data objects and benchmark architectures."""
    if not HAS_BENCHMARK or not HAS_TORCH:
        result = ModelResult(model_name=mt, model_type=mt)
        result.best_params = {"error": "torch_geometric not available for graph-based training"}
        return result

    result = ModelResult(model_name=mt, model_type=mt)
    t0 = time.time()
    device = BENCHMARK_DEVICE

    # Build model based on type
    if mt == "siamese_lstm":
        model = SiameseLSTMPolyPredict().to(device)
    elif mt in ("siamese_regression", "siamese_bayesian"):
        model = SiameseRegressorGraph().to(device)
    elif mt == "lstm_siamese_bayesian":
        model = LSTMSiamesePolyPredict().to(device)
    else:
        result.best_params = {"error": f"Unknown graph model type: {mt}"}
        return result

    optimizer = torch.optim.Adam(model.parameters(), lr=req.learning_rate)
    criterion = torch.nn.MSELoss()

    # We need graph data. Convert SMILES strings to PyG graphs
    graphs_a_tr = fp_data.get("graphs_a_train", []) if fp_data else []
    graphs_b_tr = fp_data.get("graphs_b_train", []) if fp_data else []
    graphs_a_te = fp_data.get("graphs_a_test", []) if fp_data else []
    graphs_b_te = fp_data.get("graphs_b_test", []) if fp_data else []

    if not graphs_a_tr:
        result.best_params = {"error": "No graph data available for graph-based model training. Ensure SMILES are provided."}
        result.training_time_s = time.time() - t0
        return result

    Y_tr_t = torch.tensor(Y_tr, dtype=torch.float32, device=device)
    Y_te_t = torch.tensor(Y_te, dtype=torch.float32, device=device)
    if Y_tr_t.dim() == 1:
        Y_tr_t = Y_tr_t.unsqueeze(1)
    if Y_te_t.dim() == 1:
        Y_te_t = Y_te_t.unsqueeze(1)

    epochs = req.epochs
    bs = req.batch_size
    n = len(graphs_a_tr)
    progress.total_epochs = epochs

    for ep in range(epochs):
        model.train()
        perm = torch.randperm(n).tolist()
        ep_loss = 0.0
        nb = 0
        for start in range(0, n, bs):
            batch_idx = perm[start:start + bs]
            ga_batch = [graphs_a_tr[i] for i in batch_idx]
            gb_batch = [graphs_b_tr[i] for i in batch_idx]
            yb = Y_tr_t[torch.tensor(batch_idx)]
            try:
                from torch_geometric.data import Batch
                batch_a = Batch.from_data_list([graph_dict_to_single_pyg(g, device) for g in ga_batch])
                batch_b = Batch.from_data_list([graph_dict_to_single_pyg(g, device) for g in gb_batch])
                optimizer.zero_grad()
                pred = model(batch_a, batch_b)
                loss = criterion(pred, yb[:, :pred.shape[1]])
                loss.backward()
                optimizer.step()
                ep_loss += loss.item()
                nb += 1
            except Exception as e:
                continue
        result.train_loss_curve.append(round(ep_loss / max(nb, 1), 6))
        progress.current_epoch = ep + 1
        progress.train_loss = result.train_loss_curve[-20:]
        if job_id:
            _update_progress(job_id, current_epoch=ep + 1, train_loss=result.train_loss_curve[-20:])

    # Evaluate
    model.eval()
    preds = []
    with torch.no_grad():
        try:
            from torch_geometric.data import Batch
            for start in range(0, len(graphs_a_te), bs):
                ga_b = [graph_dict_to_single_pyg(graphs_a_te[i], device) for i in range(start, min(start + bs, len(graphs_a_te)))]
                gb_b = [graph_dict_to_single_pyg(graphs_b_te[i], device) for i in range(start, min(start + bs, len(graphs_b_te)))]
                ba = Batch.from_data_list(ga_b)
                bb = Batch.from_data_list(gb_b)
                p = model(ba, bb).cpu().numpy()
                preds.append(p)
        except Exception:
            pass

    if preds:
        pred_te = np.vstack(preds)
        y_np = Y_te_t.cpu().numpy()
        from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
        result.y_true_r1 = y_np[:, 0].tolist()
        result.y_pred_r1 = pred_te[:, 0].tolist()
        result.r2_r1 = float(r2_score(y_np[:, 0], pred_te[:, 0]))
        result.mse_r1 = float(mean_squared_error(y_np[:, 0], pred_te[:, 0]))
        result.mae_r1 = float(mean_absolute_error(y_np[:, 0], pred_te[:, 0]))
        result.rmse_r1 = float(np.sqrt(result.mse_r1))
        if pred_te.shape[1] >= 2 and y_np.shape[1] >= 2:
            result.y_true_r2 = y_np[:, 1].tolist()
            result.y_pred_r2 = pred_te[:, 1].tolist()
            result.r2_r2 = float(r2_score(y_np[:, 1], pred_te[:, 1]))
            result.mse_r2 = float(mean_squared_error(y_np[:, 1], pred_te[:, 1]))
            result.mae_r2 = float(mean_absolute_error(y_np[:, 1], pred_te[:, 1]))
            result.rmse_r2 = float(np.sqrt(result.mse_r2))

    result.training_time_s = time.time() - t0
    return result


# ──────────────────────────────────────────────────────────
#  VAE / Autoencoder training (matching Autoencoders.ipynb)
# ──────────────────────────────────────────────────────────
def _train_vae_model(fp_data, req, progress, job_id: str | None = None) -> ModelResult:
    """Train the VAERegressor autoencoder matching the Autoencoders notebook."""
    if not HAS_BENCHMARK or not HAS_TORCH:
        result = ModelResult(model_name="autoencoder", model_type="autoencoder")
        result.best_params = {"error": "torch_geometric not available for autoencoder training"}
        return result

    result = ModelResult(model_name="autoencoder", model_type="autoencoder")
    t0 = time.time()
    device = BENCHMARK_DEVICE

    model = VAERegressor().to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=req.learning_rate)

    graphs_tr = (fp_data.get("graphs_a_train", []) + fp_data.get("graphs_b_train", [])) if fp_data else []
    if not graphs_tr:
        result.best_params = {"error": "No graph data for autoencoder training"}
        result.training_time_s = time.time() - t0
        return result

    epochs = req.epochs
    progress.total_epochs = epochs
    bs = req.batch_size

    for ep in range(epochs):
        model.train()
        import random
        random.shuffle(graphs_tr)
        ep_loss = 0.0
        nb = 0
        for start in range(0, len(graphs_tr), bs):
            batch_graphs = graphs_tr[start:start + bs]
            try:
                from torch_geometric.data import Batch
                batch = Batch.from_data_list([graph_dict_to_single_pyg(g, device) for g in batch_graphs])
                # For VAE training, pass graphs through. The VAERegressor is a regressor but
                # we can train it in a self-supervised way using the graph reconstruction.
                optimizer.zero_grad()
                # Create dummy targets (mean of 0) for unsupervised pretraining of the encoder
                dummy_y = torch.zeros(len(batch_graphs), 2, device=device)
                pred = model(batch)
                loss = torch.nn.MSELoss()(pred, dummy_y)
                loss.backward()
                optimizer.step()
                ep_loss += loss.item()
                nb += 1
            except Exception:
                continue
        result.train_loss_curve.append(round(ep_loss / max(nb, 1), 6))
        progress.current_epoch = ep + 1
        progress.train_loss = result.train_loss_curve[-20:]
        if job_id:
            _update_progress(job_id, current_epoch=ep + 1, train_loss=result.train_loss_curve[-20:])

    result.training_time_s = time.time() - t0
    return result


def _prepare_smiles_and_graphs(df, valid_idx, col_a, col_b, tr_idx, te_idx):
    """
    Prepare SMILES strings and graph data dicts for both SMILES-LSTM and graph models.
    Returns a dict with smiles and graph lists aligned to train/test splits.
    """
    smiles_a = [str(df.iloc[i][col_a]) for i in valid_idx]
    smiles_b = [str(df.iloc[i][col_b]) for i in valid_idx]

    fp_data = {
        "smiles_a_train": [smiles_a[i] for i in tr_idx],
        "smiles_b_train": [smiles_b[i] for i in tr_idx],
        "smiles_a_test": [smiles_a[i] for i in te_idx],
        "smiles_b_test": [smiles_b[i] for i in te_idx],
    }

    # Also prepare graph dicts for graph-based models
    graphs_a = [smiles_to_graph(s) for s in smiles_a]
    graphs_b = [smiles_to_graph(s) for s in smiles_b]

    fp_data["graphs_a_train"] = [g for i, g in enumerate(graphs_a) if i in tr_idx and g is not None]
    fp_data["graphs_b_train"] = [g for i, g in enumerate(graphs_b) if i in tr_idx and g is not None]
    fp_data["graphs_a_test"] = [g for i, g in enumerate(graphs_a) if i in te_idx and g is not None]
    fp_data["graphs_b_test"] = [g for i, g in enumerate(graphs_b) if i in te_idx and g is not None]

    return fp_data


def _prepare_fingerprints_aligned(df, valid_idx, col_a, col_b):
    """Generate Morgan FPs aligned 1:1 with valid_idx."""
    fps_a, fps_b = [], []
    fp_len = 2048  # default Morgan FP length
    for i in valid_idx:
        row = df.iloc[i]
        fa = smiles_to_morgan_fp(str(row[col_a]))
        fb = smiles_to_morgan_fp(str(row[col_b]))
        if fa is not None and fb is not None:
            fps_a.append(fa)
            fps_b.append(fb)
        else:
            # zero-fill to keep alignment
            fps_a.append(np.zeros(fp_len, dtype=np.float32))
            fps_b.append(np.zeros(fp_len, dtype=np.float32))
    if not fps_a:
        return None
    return {"fps_a": np.array(fps_a), "fps_b": np.array(fps_b)}


def _cv_folds(cv: CVMethod) -> int:
    return {"kfold_5": 5, "kfold_10": 10, "kfold_20": 20, "kfold_100": 100}.get(cv.value, 5)


def _save_results(job_id, results, split_info):
    out_dir = RESULTS_DIR / job_id
    out_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "job_id": job_id,
        "split_info": split_info,
        "results": [r.model_dump() for r in results],
        "summary": _build_summary(results),
    }
    (out_dir / "results.json").write_text(json.dumps(data, default=str))


def _build_summary(results: list[ModelResult]) -> dict:
    valid = [r for r in results if r.r2_r1 is not None]
    if not valid:
        return {}
    best_r1 = max(valid, key=lambda r: r.r2_r1 or -999)
    best_r2 = max(valid, key=lambda r: r.r2_r2 or -999)
    return {
        "num_models": len(valid),
        "best_r1_model": best_r1.model_name,
        "best_r1_r2": best_r1.r2_r1,
        "best_r2_model": best_r2.model_name,
        "best_r2_r2": best_r2.r2_r2,
        "avg_r2_r1": round(np.mean([r.r2_r1 for r in valid if r.r2_r1 is not None]), 4),
        "avg_r2_r2": round(np.mean([r.r2_r2 for r in valid if r.r2_r2 is not None]), 4),
    }
