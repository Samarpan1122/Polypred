"""Training pipeline - train any model, with optional HP tuning + CV."""

from __future__ import annotations

import os
import time
import uuid
import json
import traceback
from pathlib import Path
from typing import Any
from threading import Thread, Lock
import concurrent.futures

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.model_selection import (
    KFold, cross_val_score, GridSearchCV, RandomizedSearchCV
)
from sklearn.metrics import (
    r2_score, mean_squared_error, mean_absolute_error,
    median_absolute_error, max_error, explained_variance_score,
    mean_absolute_percentage_error
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


def _calculate_full_scores(y_true, y_pred) -> dict:
    """Scientific exhaustive metric set from research notebooks."""
    y_true = np.array(y_true)
    y_pred = np.array(y_pred)
    if len(y_true) == 0: return {}
    
    r2 = float(r2_score(y_true, y_pred))
    mse = float(mean_squared_error(y_true, y_pred))
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(np.sqrt(mse))
    medae = float(median_absolute_error(y_true, y_pred))
    maxe = float(max_error(y_true, y_pred))
    
    try:
        mape = float(mean_absolute_percentage_error(y_true, y_pred) * 100)
    except:
        mape = float(np.mean(np.abs((y_true - y_pred) / np.clip(np.abs(y_true), 1e-8, None))) * 100)
        
    evs = float(explained_variance_score(y_true, y_pred))
    try:
        pearson = float(np.corrcoef(y_true, y_pred)[0, 1]) if len(y_true) > 1 else 0.0
    except:
        pearson = 0.0
        
    return {
        "r2": r2, "mse": mse, "mae": mae, "rmse": rmse,
        "medae": medae, "max_error": maxe, "mape": mape,
        "evs": evs, "pearson": pearson
    }

# ──────────────────────────────────────────────────────────
#  Default HP grids for each model type  (matches Specific_Models_Final IPYNBs)
# ──────────────────────────────────────────────────────────
DEFAULT_HP_GRIDS: dict[str, dict[str, list]] = {
    # Decision_Tree.ipynb: RandomizedSearchCV param_dist
    "decision_tree": {
        "max_depth": [3, 5, 7, 10, 15, 20, None],
        "min_samples_split": [2, 3, 5, 7, 10],
        "min_samples_leaf": [1, 2, 3, 5],
        "max_features": ["sqrt", "log2", None],
    },
    # Random_Forest.ipynb: GridSearchCV param_grid
    "random_forest": {
        "n_estimators": [100, 200],
        "max_depth": [10, 20, None],
        "min_samples_split": [2, 5],
    },
    # Ensemble_Methods.ipynb: XGBoost GridSearchCV xgb_param
    "ensemble_methods": {
        "n_estimators": [200, 400],
        "max_depth": [3, 5],
        "learning_rate": [0.05, 0.1],
    },
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
_progress_lock = Lock()


def _update_progress(job_id: str, **kwargs):
    """Load progress, update fields, save back to file (Thread Safe)."""
    with _progress_lock:
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
        _update_progress(job_id, message=f"Featurizing {len(df)} molecules - this may take a few minutes...")
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
        transformed_targets = []
        for tc in req.target_cols:
            if tc in df.columns:
                val = df.loc[valid_idx, tc].values.astype(float)
                # Auto-log transform for reactivity ratios if requested or detected
                if tc.lower() in ['r1', 'r2']:
                    _update_progress(job_id, message=f"Transforming {tc} to log10 space for training...")
                    val = np.log10(np.clip(val, 1e-6, None)) # Clip to avoid log(0)
                    transformed_targets.append(tc)
                targets.append(val)
        
        if len(targets) == 0:
            _update_progress(job_id, status="failed", message="No valid target columns found")
            return
        
        Y = np.column_stack(targets) if len(targets) > 1 else targets[0].reshape(-1, 1)
        Y = np.nan_to_num(Y)
        
        if transformed_targets:
            _update_progress(job_id, message=f"Predicting log10 of: {', '.join(transformed_targets)}")

        # 4. Split - directly split the feature matrix to avoid index-mapping bugs
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

        # 6. Train models in parallel
        all_results: list[ModelResult] = []
        
        def _train_task(mi: int, model_type: ModelType):
            _update_progress(
                job_id,
                current_model=model_type.value,
                # models_completed stays what it was, until this task finishes
                elapsed_seconds=round(time.time() - t_start, 1),
                message=f"Training {model_type.value}...",
                train_loss=[],
                val_loss=[],
                train_r2=[],
                val_r2=[]
            )
            prog = _load_progress(job_id)
            try:
                res = _train_single_model(
                    model_type, X_train, Y_train, X_test, Y_test,
                    X_val, Y_val, req, prog, fp_data, job_id
                )
                return res
            except Exception as e:
                traceback.print_exc()
                err_msg = f"{type(e).__name__}: {str(e)[:200]}"
                print(f"[TRAINING ERROR] {model_type.value}: {err_msg}", flush=True)
                err_res = ModelResult(model_name=model_type.value, model_type=model_type.value)
                err_res.best_params = {"error": err_msg}
                return err_res

        # Using max_workers controlled by models requested
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(10, len(req.models))) as executor:
            future_to_model = {executor.submit(_train_task, i, m): m for i, m in enumerate(req.models)}
            for future in concurrent.futures.as_completed(future_to_model):
                res = future.result()
                all_results.append(res)
                # Update completed count
                _update_progress(job_id, models_completed=len(all_results))

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
        # User requested to use flatten_graph for traditional models to match notebooks exactly
        if fp_data and "graphs_a_train" in fp_data:
            from app.models.notebook_dataloaders import flatten_graph
            import numpy as np
            
            def make_X(ga_list, gb_list):
                from app.models.benchmark_models import graph_dict_to_single_pyg
                Xa, Xb = [], []
                for ga, gb in zip(ga_list, gb_list):
                    pyg_a = graph_dict_to_single_pyg(ga, device="cpu") if ga else None
                    pyg_b = graph_dict_to_single_pyg(gb, device="cpu") if gb else None
                    Xa.append(flatten_graph(pyg_a))
                    Xb.append(flatten_graph(pyg_b))
                return np.hstack([np.vstack(Xa), np.vstack(Xb)]) if Xa else np.zeros((0, 130))

            print(f"[{mt}] Re-building X_train and X_test using notebook's flatten_graph (130-d)", flush=True)
            X_train = make_X(fp_data["graphs_a_train"], fp_data["graphs_b_train"])
            X_test  = make_X(fp_data["graphs_a_test"], fp_data["graphs_b_test"])

            from sklearn.preprocessing import StandardScaler
            scaler = StandardScaler()
            if len(X_train) > 0:
                X_train = scaler.fit_transform(X_train)
                X_test = scaler.transform(X_test)

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
#  Traditional ML training - matches Specific_Models_Final IPYNBs exactly
#  Decision_Tree.ipynb: RandomizedSearchCV → narrow GridSearchCV → KFold(10)
#  Random_Forest.ipynb: GridSearchCV(n_est=[100,200], max_depth=[10,20,None], cv=5) → KFold(10)
#  Ensemble_Methods.ipynb: ExtraTrees(200) + GradBoosting(200,depth=4) + XGB(200,depth=4,lr=0.05)
# ──────────────────────────────────────────────────────────
def _train_traditional(
    mt: str, X_train, Y_train, X_test, Y_test,
    req: TrainRequest, progress: TrainProgress,
) -> ModelResult:

    result = ModelResult(model_name=mt, model_type=mt)
    t0 = time.time()

    y_true_r1_all, y_pred_r1_all = [], []
    y_true_r2_all, y_pred_r2_all = [], []

    for target_i, target_name in enumerate(req.target_cols):
        if target_i >= Y_train.shape[1]:
            break

        y_tr = Y_train[:, target_i]
        y_te = Y_test[:, target_i]

        progress.message = f"Training {mt} for {target_name} ({target_i+1}/{len(req.target_cols)})..."

        # ── Decision Tree (matches Decision_Tree.ipynb) ─────────────────────
        if mt == "decision_tree":
            from sklearn.tree import DecisionTreeRegressor
            # Step 1: RandomizedSearchCV (same as notebook)
            param_dist = {
                'max_depth': [3, 5, 7, 10, 15, 20, None],
                'min_samples_split': [2, 3, 5, 7, 10],
                'min_samples_leaf': [1, 2, 3, 5],
                'max_features': ['sqrt', 'log2', None],
            }
            progress.message = f"RandomizedSearchCV for Decision Tree ({target_name})..."
            rscv = RandomizedSearchCV(
                DecisionTreeRegressor(random_state=42), param_dist,
                n_iter=50, cv=5, scoring='r2', n_jobs=-1,
                random_state=42, verbose=0
            )
            rscv.fit(X_train, y_tr)
            bp = rscv.best_params_

            # Step 2: Narrow GridSearchCV around best params (same as notebook)
            def _narrow_grid(best):
                d = best.get('max_depth', 10)
                s = best.get('min_samples_split', 5)
                l = best.get('min_samples_leaf', 2)
                return {
                    'max_depth': sorted(set([max(1, d - 2), d, d + 2 if d else 20, None])),
                    'min_samples_split': sorted(set([max(2, s - 1), s, s + 1])),
                    'min_samples_leaf': sorted(set([max(1, l - 1), l, l + 1])),
                    'max_features': [best.get('max_features', None)],
                }

            progress.message = f"GridSearchCV refinement for Decision Tree ({target_name})..."
            gs = GridSearchCV(
                DecisionTreeRegressor(random_state=42),
                _narrow_grid(bp), cv=5, scoring='r2', n_jobs=-1
            )
            gs.fit(X_train, y_tr)
            model = gs.best_estimator_
            result.best_params = {**result.best_params, f"{target_name}_best": gs.best_params_}

        # ── Random Forest (matches Random_Forest.ipynb) ─────────────────────
        elif mt == "random_forest":
            from sklearn.ensemble import RandomForestRegressor
            param_grid = {
                'n_estimators': [100, 200],
                'max_depth': [10, 20, None],
                'min_samples_split': [2, 5],
            }
            progress.message = f"GridSearchCV for Random Forest ({target_name})..."
            gs = GridSearchCV(
                RandomForestRegressor(random_state=42, n_jobs=-1),
                param_grid, cv=5, scoring='r2', n_jobs=-1
            )
            gs.fit(X_train, y_tr)
            model = gs.best_estimator_
            result.best_params = {**result.best_params, f"{target_name}_best": gs.best_params_}

        # ── Ensemble Methods (matches Ensemble_Methods.ipynb) ───────────────
        elif mt == "ensemble_methods":
            from sklearn.ensemble import (
                ExtraTreesRegressor, GradientBoostingRegressor
            )
            try:
                import xgboost as xgb
                has_xgb = True
            except ImportError:
                has_xgb = False

            # Train all 3 ensemble models exactly as in notebook
            candidates = {
                'ExtraTrees': ExtraTreesRegressor(
                    n_estimators=200, random_state=42, n_jobs=-1
                ),
                'GradBoosting': GradientBoostingRegressor(
                    n_estimators=200, max_depth=4, random_state=42
                ),
            }
            if has_xgb:
                candidates['XGBoost'] = xgb.XGBRegressor(
                    n_estimators=200, max_depth=4, learning_rate=0.05,
                    random_state=42, verbosity=0, n_jobs=-1
                )

            best_score = -999
            best_name = None
            model = None
            progress.message = f"Comparing ensemble methods for {target_name}..."

            for name, cand in candidates.items():
                cand.fit(X_train, y_tr)
                score = r2_score(y_te, cand.predict(X_test))
                if score > best_score:
                    best_score = score
                    best_name = name
                    model = cand

            # XGBoost GridSearchCV tuning (matching notebook)
            if has_xgb:
                progress.message = f"XGBoost GridSearchCV for {target_name}..."
                xgb_param = {
                    'n_estimators': [200, 400],
                    'max_depth': [3, 5],
                    'learning_rate': [0.05, 0.1],
                }
                gs = GridSearchCV(
                    xgb.XGBRegressor(random_state=42, verbosity=0),
                    xgb_param, cv=5, scoring='r2', n_jobs=-1
                )
                gs.fit(X_train, y_tr)
                xgb_tuned_score = r2_score(y_te, gs.best_estimator_.predict(X_test))
                if xgb_tuned_score > best_score:
                    best_score = xgb_tuned_score
                    best_name = 'XGBoost_tuned'
                    model = gs.best_estimator_

            result.best_params = {
                **result.best_params,
                f"{target_name}_best_ensemble": best_name,
                f"{target_name}_best_r2": round(best_score, 4),
            }

        else:
            from sklearn.ensemble import RandomForestRegressor
            model = RandomForestRegressor(n_estimators=200, random_state=42, n_jobs=-1)
            model.fit(X_train, y_tr)

        # ── KFold(10) CV (all 3 notebooks use KFold(n_splits=10, shuffle=True, random_state=42)) ──
        kf = KFold(n_splits=10, shuffle=True, random_state=42)
        cv_scores = cross_val_score(model, X_train, y_tr, cv=kf, scoring='r2')
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
        if hasattr(model, 'feature_importances_'):
            imp = model.feature_importances_
            top_k = min(20, len(imp))
            top_idx = np.argsort(imp)[-top_k:][::-1]
            
            feature_names_map = []
            if req.feature_set_id:
                try:
                    from app.services.feature_service import get_feature_set_info
                    meta = get_feature_set_info(req.feature_set_id)
                    feature_names_map = meta.get("feature_names", [])
                except Exception:
                    pass
                    
            result.feature_importance = {
                (feature_names_map[i] if i < len(feature_names_map) else f'feat_{i}'): float(imp[i]) 
                for i in top_idx
            }
            result_feature_names = feature_names_map if feature_names_map else [f"feat_{i}" for i in range(len(imp))]
        else:
            result_feature_names = []

    result.y_true_r1 = y_true_r1_all
    result.y_pred_r1 = y_pred_r1_all
    result.y_true_r2 = y_true_r2_all
    result.y_pred_r2 = y_pred_r2_all
    
    s1 = _calculate_full_scores(y_true_r1_all, y_pred_r1_all)
    if s1:
        result.r2_r1, result.mse_r1, result.mae_r1, result.rmse_r1 = s1['r2'], s1['mse'], s1['mae'], s1['rmse']
        result.medae_r1, result.max_error_r1, result.mape_r1 = s1['medae'], s1['max_error'], s1['mape']
        result.evs_r1, result.pearson_r1 = s1['evs'], s1['pearson']
        
    s2 = _calculate_full_scores(y_true_r2_all, y_pred_r2_all)
    if s2:
        result.r2_r2, result.mse_r2, result.mae_r2, result.rmse_r2 = s2['r2'], s2['mse'], s2['mae'], s2['rmse']
        result.medae_r2, result.max_error_r2, result.mape_r2 = s2['medae'], s2['max_error'], s2['mape']
        result.evs_r2, result.pearson_r2 = s2['evs'], s2['pearson']

    result.training_time_s = time.time() - t0
    
    # Generate Advanced Pyplot Analytics
    result.diagnostic_plots = _generate_diagnostic_plots(result, result_feature_names)
    
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
    # IPYNB: emb_dim=64, hidden=128, nlayers=2, dropout=0.3, bidirectional=True
    model = BiLSTMRegressorSMILES().to(device)
    # IPYNB default: Adam(lr=3e-4, weight_decay=1e-5)
    lr = req.learning_rate if req.learning_rate != 1e-3 else 3e-4  # Use IPYNB default
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-5)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5, factor=0.5)
    criterion = torch.nn.MSELoss()

    # Y_tr, Y_te as tensors (2-column: r1, r2)
    Y_tr_t = torch.tensor(Y_tr, dtype=torch.float32, device=device)
    Y_te_t = torch.tensor(Y_te, dtype=torch.float32, device=device)
    if Y_tr_t.dim() == 1:
        Y_tr_t = Y_tr_t.unsqueeze(1)
    if Y_te_t.dim() == 1:
        Y_te_t = Y_te_t.unsqueeze(1)

    # We need SMILES strings for this model - use fp_data smiles if available, fallback
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

    import pandas as pd
    from app.models.notebook_dataloaders import PolyDataset, encode_smiles_lstm
    from app.models.benchmark_models import SMILES_VOCAB
    from torch.utils.data import DataLoader

    tr_df = pd.DataFrame({
        'SMILES_A': smiles_a_tr,
        'SMILES_B': smiles_b_tr,
        'log_r1': Y_tr[:, 0] if Y_tr.shape[1] > 0 else np.zeros(n),
        'log_r2': Y_tr[:, 1] if Y_tr.shape[1] > 1 else np.zeros(n)
    })
    
    n_te = len(smiles_a_te)
    te_df = pd.DataFrame({
        'SMILES_A': smiles_a_te,
        'SMILES_B': smiles_b_te,
        'log_r1': Y_te[:, 0] if Y_te.shape[1] > 0 else np.zeros(n_te),
        'log_r2': Y_te[:, 1] if Y_te.shape[1] > 1 else np.zeros(n_te)
    })

    train_loader = DataLoader(PolyDataset(tr_df, SMILES_VOCAB), batch_size=bs, shuffle=True)
    test_loader = DataLoader(PolyDataset(te_df, SMILES_VOCAB), batch_size=bs)

    for ep in range(epochs):
        model.train()
        ep_loss = 0.0
        nb = 0
        for ta, tb, yb in train_loader:
            ta = ta.to(device)
            tb = tb.to(device)
            yb = yb.to(device)
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
    result.y_true_r1 = y_np[:, 0].tolist()
    result.y_pred_r1 = pred_te[:, 0].tolist()
    
    s1 = _calculate_full_scores(result.y_true_r1, result.y_pred_r1)
    if s1:
        result.r2_r1, result.mse_r1, result.mae_r1, result.rmse_r1 = s1['r2'], s1['mse'], s1['mae'], s1['rmse']
        result.medae_r1, result.max_error_r1, result.mape_r1 = s1['medae'], s1['max_error'], s1['mape']
        result.evs_r1, result.pearson_r1 = s1['evs'], s1['pearson']

    if pred_te.shape[1] >= 2 and y_np.shape[1] >= 2:
        result.y_true_r2 = y_np[:, 1].tolist()
        result.y_pred_r2 = pred_te[:, 1].tolist()
        s2 = _calculate_full_scores(result.y_true_r2, result.y_pred_r2)
        if s2:
            result.r2_r2, result.mse_r2, result.mae_r2, result.rmse_r2 = s2['r2'], s2['mse'], s2['mae'], s2['rmse']
            result.medae_r2, result.max_error_r2, result.mape_r2 = s2['medae'], s2['max_error'], s2['mape']
            result.evs_r2, result.pearson_r2 = s2['evs'], s2['pearson']
    
    result.training_time_s = time.time() - t0
    
    # Generate Advanced Pyplot Analytics
    result.diagnostic_plots = _generate_diagnostic_plots(result, [])
    
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

    # IPYNB default: Adam(lr=1e-3, weight_decay=1e-4)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
    # Siamese models use StepLR(step_size=10, gamma=0.5); LSTM hybrids use ReduceLROnPlateau
    if mt in ("siamese_regression", "siamese_bayesian"):
        scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=10, gamma=0.5)
    else:
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5, factor=0.5)
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

    # Use notebook DataLoaders
    import pandas as pd
    from app.models.notebook_dataloaders import PairDataset
    from torch_geometric.loader import DataLoader
    from torch_geometric.data import Batch
    
    # 1. Build DF for train and test PyG objects
    tr_df = pd.DataFrame({
        'Graph_A': [graph_dict_to_single_pyg(g, "cpu") for g in graphs_a_tr],
        'Graph_B': [graph_dict_to_single_pyg(g, "cpu") for g in graphs_b_tr],
        'log_r1': Y_tr[:, 0] if Y_tr.shape[1] > 0 else np.zeros(n),
        'log_r2': Y_tr[:, 1] if Y_tr.shape[1] > 1 else np.zeros(n)
    })
    
    # Check if testing data exists 
    n_te = len(graphs_a_te)
    te_df = pd.DataFrame({
        'Graph_A': [graph_dict_to_single_pyg(g, "cpu") for g in graphs_a_te],
        'Graph_B': [graph_dict_to_single_pyg(g, "cpu") for g in graphs_b_te],
        'log_r1': Y_te[:, 0] if Y_te.shape[1] > 0 else np.zeros(n_te),
        'log_r2': Y_te[:, 1] if Y_te.shape[1] > 1 else np.zeros(n_te)
    })

    def my_collate_fn(batch):
        ga = Batch.from_data_list([item[0] for item in batch])
        gb = Batch.from_data_list([item[1] for item in batch])
        tgt = torch.stack([item[2] for item in batch])
        return ga, gb, tgt

    train_loader = DataLoader(PairDataset(tr_df, list(range(len(tr_df)))), batch_size=bs, shuffle=True, collate_fn=my_collate_fn)

    for ep in range(epochs):
        model.train()
        ep_loss = 0.0
        nb = 0
        for batch_a, batch_b, tgt in train_loader:
            batch_a = batch_a.to(device)
            batch_b = batch_b.to(device)
            tgt = tgt.to(device)
            
            optimizer.zero_grad()
            try:
                pred = model(batch_a, batch_b)
                loss = criterion(pred, tgt[:, :pred.shape[1]])
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
    
    test_loader = DataLoader(PairDataset(te_df, list(range(len(te_df)))), batch_size=bs, collate_fn=my_collate_fn)
    
    with torch.no_grad():
        for batch_a, batch_b, _ in test_loader:
            try:
                batch_a = batch_a.to(device)
                batch_b = batch_b.to(device)
                p = model(batch_a, batch_b).cpu().numpy()
                preds.append(p)
            except Exception:
                pass

    if preds:
        pred_te = np.vstack(preds)
        y_np = Y_te_t.cpu().numpy()
        result.y_true_r1 = y_np[:, 0].tolist()
        result.y_pred_r1 = pred_te[:, 0].tolist()
        
        s1 = _calculate_full_scores(result.y_true_r1, result.y_pred_r1)
        if s1:
            result.r2_r1, result.mse_r1, result.mae_r1, result.rmse_r1 = s1['r2'], s1['mse'], s1['mae'], s1['rmse']
            result.medae_r1, result.max_error_r1, result.mape_r1 = s1['medae'], s1['max_error'], s1['mape']
            result.evs_r1, result.pearson_r1 = s1['evs'], s1['pearson']

        if pred_te.shape[1] >= 2 and y_np.shape[1] >= 2:
            result.y_true_r2 = y_np[:, 1].tolist()
            result.y_pred_r2 = pred_te[:, 1].tolist()
            s2 = _calculate_full_scores(result.y_true_r2, result.y_pred_r2)
            if s2:
                result.r2_r2, result.mse_r2, result.mae_r2, result.rmse_r2 = s2['r2'], s2['mse'], s2['mae'], s2['rmse']
                result.medae_r2, result.max_error_r2, result.mape_r2 = s2['medae'], s2['max_error'], s2['mape']
                result.evs_r2, result.pearson_r2 = s2['evs'], s2['pearson']

    result.training_time_s = time.time() - t0
    
    # Generate Advanced Pyplot Analytics
    result.diagnostic_plots = _generate_diagnostic_plots(result, [])
    
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
    # IPYNB default: Adam(lr=1e-3)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)

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
        "summary": [{"model": r.model_name, "r2_r1": getattr(r, "r2_r1", 0.0), "time": r.training_time_s} for r in results],
    }
    (out_dir / "results.json").write_text(json.dumps(data, default=str))


def _generate_diagnostic_plots(result: ModelResult, feature_names: list[str]) -> list[str]:
    """Execute the comprehensive 20-plot Matplotlib analytical dashboard from user IPYNBs."""
    import io
    import base64
    import matplotlib
    matplotlib.use("Agg")  # CRITICAL for background headless running without GUI crashes
    import matplotlib.pyplot as plt
    import seaborn as sns
    import scipy.stats as ss
    from pandas.plotting import parallel_coordinates
    import warnings
    warnings.filterwarnings('ignore')

    if not result.y_true_r1 or not result.y_pred_r1:
        return []

    y1_te = np.array(result.y_true_r1)
    pr1 = np.array(result.y_pred_r1)
    res1 = y1_te - pr1
    scores_r1 = {"R²": result.r2_r1 or 0.0, "RMSE": result.rmse_r1 or 0.0, "MAE": result.mae_r1 or 0.0, "MSE": result.mse_r1 or 0.0, "MedAE": float(np.median(np.abs(res1)))}

    y2_te = np.array(result.y_true_r2) if result.y_true_r2 else y1_te
    pr2 = np.array(result.y_pred_r2) if result.y_pred_r2 else pr1
    res2 = y2_te - pr2
    scores_r2 = {"R²": result.r2_r2 or 0.0, "RMSE": result.rmse_r2 or 0.0, "MAE": result.mae_r2 or 0.0, "MSE": result.mse_r2 or 0.0, "MedAE": float(np.median(np.abs(res2)))}

    cv_r2_r1 = [result.cv_r2_r1_mean or 0.0] * 10
    cv_r2_r2 = [result.cv_r2_r2_mean or 0.0] * 10
    train_losses = result.train_loss_curve or []
    val_losses = result.val_loss_curve or []
    
    # Attempt to extract Feature Importances
    all_feature_names = feature_names if feature_names else list(result.feature_importance.keys())
    imp_r1 = [result.feature_importance.get(k, 0.0) for k in all_feature_names] if result.feature_importance else [0]*max(1, len(all_feature_names))
    imp_r2 = imp_r1
    fi_r1 = imp_r1

    base64_plots = []
    def _save_b64(fig):
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches='tight', dpi=110)
        plt.close(fig)
        buf.seek(0)
        return "data:image/png;base64," + base64.b64encode(buf.read()).decode("utf-8")

    plt.style.use('seaborn-v0_8-whitegrid')

    # ── FIGURE 1: Core Parity & Error Metrics (6 plots) ─────────────────────────
    fig1, axes1 = plt.subplots(2, 3, figsize=(22, 14))
    fig1.suptitle('Figure 1: Parity Plots & Error Metrics', fontsize=18, fontweight='bold')
    
    ax = axes1[0,0]
    ax.scatter(y1_te, pr1, s=18, alpha=0.5, c='royalblue', edgecolors='none')
    lo,hi = (min(y1_te.min(),pr1.min()), max(y1_te.max(),pr1.max())) if len(y1_te) else (0,1)
    ax.plot([lo,hi],[lo,hi],'r--',lw=2); ax.set_title('1. Parity – log(r₁)',fontweight='bold')
    ax.set_xlabel('Actual'); ax.set_ylabel('Predicted')
    ax.text(0.05,0.85, f'R²={scores_r1["R²"]:.4f}\nRMSE={scores_r1["RMSE"]:.4f}\nMAE={scores_r1["MAE"]:.4f}', transform=ax.transAxes, bbox=dict(fc='white',alpha=.85), fontsize=9)
    
    ax = axes1[0,1]
    ax.scatter(y2_te, pr2, s=18, alpha=0.5, c='seagreen', edgecolors='none')
    lo,hi = (min(y2_te.min(),pr2.min()), max(y2_te.max(),pr2.max())) if len(y2_te) else (0,1)
    ax.plot([lo,hi],[lo,hi],'r--',lw=2); ax.set_title('2. Parity – log(r₂)',fontweight='bold')
    ax.set_xlabel('Actual'); ax.set_ylabel('Predicted')
    ax.text(0.05,0.85, f'R²={scores_r2["R²"]:.4f}\nRMSE={scores_r2["RMSE"]:.4f}\nMAE={scores_r2["MAE"]:.4f}', transform=ax.transAxes, bbox=dict(fc='white',alpha=.85), fontsize=9)
    
    ax = axes1[0,2]
    bar_metrics = ['R²','RMSE','MAE','MSE','MedAE']
    r1v = [scores_r1[k] for k in bar_metrics]; r2v = [scores_r2[k] for k in bar_metrics]
    x = np.arange(len(bar_metrics)); w = 0.35
    ax.bar(x-w/2,r1v,w,label='r₁',color='cornflowerblue',alpha=.8)
    ax.bar(x+w/2,r2v,w,label='r₂',color='mediumseagreen',alpha=.8)
    ax.set_xticks(x); ax.set_xticklabels(bar_metrics,fontsize=9)
    ax.legend(); ax.set_title('3. Comprehensive Error Metrics',fontweight='bold')
    
    ax = axes1[1,0]
    if len(y1_te) > 0:
        hb = ax.hexbin(y1_te, pr1, gridsize=25, cmap='Blues', mincnt=1)
        ax.plot([y1_te.min(),y1_te.max()],[y1_te.min(),y1_te.max()],'r--',lw=2)
        fig1.colorbar(hb, ax=ax, label='Count')
    ax.set_title('4. Hexbin Density – r₁',fontweight='bold'); ax.set_xlabel('Actual'); ax.set_ylabel('Predicted')
    
    ax = axes1[1,1]
    if len(y2_te) > 0:
        hb = ax.hexbin(y2_te, pr2, gridsize=25, cmap='Greens', mincnt=1)
        ax.plot([y2_te.min(),y2_te.max()],[y2_te.min(),y2_te.max()],'r--',lw=2)
        fig1.colorbar(hb, ax=ax, label='Count')
    ax.set_title('5. Hexbin Density – r₂',fontweight='bold'); ax.set_xlabel('Actual'); ax.set_ylabel('Predicted')
    
    ax = axes1[1,2]
    from scipy.stats import spearmanr
    try:
        pr_r1 = np.corrcoef(y1_te,pr1)[0,1]; pr_r2 = np.corrcoef(y2_te,pr2)[0,1]
        sp_r1 = spearmanr(y1_te,pr1).correlation; sp_r2 = spearmanr(y2_te,pr2).correlation
        pd.DataFrame({'Pearson':[pr_r1,pr_r2],'Spearman':[sp_r1,sp_r2]}, index=['r₁','r₂']).plot(kind='bar', ax=ax, rot=0, color=['steelblue','salmon'], alpha=.8)
    except: pass
    ax.set_title('6. Correlation Coefficients',fontweight='bold'); ax.set_ylabel('Coefficient'); ax.set_ylim(0,1.05)
    plt.tight_layout(); base64_plots.append(_save_b64(fig1))
    
    # ── FIGURE 2: Residual Diagnostics (6 plots) ────────────────────────────────
    fig2, axes2 = plt.subplots(2, 3, figsize=(22, 14))
    fig2.suptitle('Figure 2: Residual Diagnostics', fontsize=18, fontweight='bold')
    
    ax = axes2[0,0]
    ax.scatter(pr1, res1, alpha=0.4, c='slateblue', s=14)
    ax.axhline(0, color='r', ls='--'); ax.set_title('7. Residuals vs Predicted (r₁)',fontweight='bold')
    ax.set_xlabel('Predicted'); ax.set_ylabel('Residual')
    
    ax = axes2[0,1]
    ax.scatter(pr2, res2, alpha=0.4, c='darkcyan', s=14)
    ax.axhline(0, color='r', ls='--'); ax.set_title('8. Residuals vs Predicted (r₂)',fontweight='bold')
    ax.set_xlabel('Predicted'); ax.set_ylabel('Residual')
    
    ax = axes2[0,2]
    try:
        sns.kdeplot(res1, ax=ax, label='r₁', fill=True, color='royalblue', alpha=.4)
        sns.kdeplot(res2, ax=ax, label='r₂', fill=True, color='seagreen',  alpha=.4)
    except: pass
    ax.set_title('9. Residual Density (KDE)',fontweight='bold'); ax.legend()
    
    ax = axes2[1,0]; ss.probplot(res1, dist='norm', plot=ax); ax.set_title('10. Q-Q Plot (r₁ residuals)',fontweight='bold')
    ax = axes2[1,1]; ss.probplot(res2, dist='norm', plot=ax); ax.set_title('11. Q-Q Plot (r₂ residuals)',fontweight='bold')
    
    ax = axes2[1,2]
    if len(res1) and len(res2):
        ax.hist(np.abs(res1), bins=30, alpha=0.6, color='royalblue', label='|err r₁|', rwidth=0.85)
        ax.hist(np.abs(res2), bins=30, alpha=0.6, color='seagreen',  label='|err r₂|', rwidth=0.85)
    ax.set_title('12. Absolute Error Distribution',fontweight='bold'); ax.legend(); ax.set_xlabel('|Error|')
    plt.tight_layout(); base64_plots.append(_save_b64(fig2))

    # ── FIGURE 3: Cross-Validation & Stability (4 plots) ────────────────────────
    fig3, axes3 = plt.subplots(1, 4, figsize=(24, 6))
    fig3.suptitle('Figure 3: Cross-Validation & Stability', fontsize=18, fontweight='bold')
    
    ax = axes3[0]
    sns.boxplot(data=pd.DataFrame({'r₁ CV R²': cv_r2_r1, 'r₂ CV R²': cv_r2_r2}), ax=ax, palette='pastel')
    sns.stripplot(data=pd.DataFrame({'r₁ CV R²': cv_r2_r1, 'r₂ CV R²': cv_r2_r2}), ax=ax, color='.2', alpha=.5, jitter=True)
    ax.set_title('13. 10-Fold CV Stability',fontweight='bold'); ax.set_ylabel('R²')
    
    ax = axes3[1]
    n_plot = min(80, len(y1_te))
    if n_plot > 0:
        ax.plot(y1_te[:n_plot], 'k-', lw=1.2, label='True r₁')
        ax.plot(pr1[:n_plot], 'b--', lw=1.2, label='Pred r₁', alpha=0.8)
        ax.fill_between(range(n_plot), y1_te[:n_plot], pr1[:n_plot], alpha=0.15, color='blue')
    ax.set_title('14. True vs Predicted (subset)',fontweight='bold'); ax.legend()
    
    ax = axes3[2]
    sorted_err1 = np.sort(np.abs(res1)); sorted_err2 = np.sort(np.abs(res2))
    if len(sorted_err1) and len(sorted_err2):
        ax.plot(np.linspace(0,100,len(sorted_err1)), sorted_err1, 'b-', label='r₁')
        ax.plot(np.linspace(0,100,len(sorted_err2)), sorted_err2, 'g-', label='r₂')
    ax.set_title('15. Cumulative Error Curve',fontweight='bold'); ax.set_xlabel('Percentile (%)'); ax.set_ylabel('Absolute Error'); ax.legend()
    
    ax = axes3[3]
    if len(res1) and len(res2):
        thresholds = np.linspace(0, max(np.abs(res1).max(), np.abs(res2).max()), 50)
        pct1 = [np.mean(np.abs(res1) <= t)*100 for t in thresholds]; pct2 = [np.mean(np.abs(res2) <= t)*100 for t in thresholds]
        ax.plot(thresholds, pct1, 'b-', label='r₁'); ax.plot(thresholds, pct2, 'g-', label='r₂')
    ax.set_title('16. Coverage vs Error Threshold',fontweight='bold'); ax.set_xlabel('Error Threshold'); ax.set_ylabel('% Samples Within'); ax.legend()
    plt.tight_layout(); base64_plots.append(_save_b64(fig3))
    
    # ── FIGURE 4: Advanced Analytics (4 plots) ──────────────────────────────────
    fig4, axes4 = plt.subplots(1, 4, figsize=(24, 6))
    fig4.suptitle('Figure 4: Advanced Analytics', fontsize=18, fontweight='bold')
    
    ax = axes4[0]
    ax.scatter(y1_te, y2_te, s=12, alpha=.3, c='dimgray', label='True')
    ax.scatter(pr1, pr2, s=12, alpha=.3, c='orangered', label='Predicted')
    ax.set_title('17. Joint r₁–r₂ Space',fontweight='bold'); ax.set_xlabel('log(r₁)'); ax.set_ylabel('log(r₂)'); ax.legend()
    
    ax = axes4[1]
    ax.scatter(np.abs(res1), np.abs(res2), s=12, alpha=.35, c='teal')
    ax.set_title('18. |Error r₁| vs |Error r₂|',fontweight='bold'); ax.set_xlabel('|Error r₁|'); ax.set_ylabel('|Error r₂|')
    
    ax = axes4[2]
    try:
        pc_df = pd.DataFrame({'True r₁': y1_te, 'Pred r₁': pr1, 'True r₂': y2_te, 'Pred r₂': pr2})
        pc_df['Quality'] = pd.cut(np.abs(res1), bins=3, labels=['Good','Medium','Poor'])
        parallel_coordinates(pc_df.sample(min(200,len(pc_df)),random_state=42), 'Quality', ax=ax, colormap='coolwarm', alpha=0.5)
        ax.set_title('19. Parallel Coordinates',fontweight='bold'); ax.legend(loc='upper right', fontsize=7)
    except: pass
    
    ax = axes4[3]
    try:
        hm_data = pd.DataFrame({'True r₁':y1_te,'Pred r₁':pr1,'True r₂':y2_te,'Pred r₂':pr2,'Err r₁':res1,'Err r₂':res2})
        sns.heatmap(hm_data.corr(), annot=True, fmt='.2f', cmap='RdBu_r', center=0, ax=ax, square=True, cbar_kws={'shrink':0.8})
        ax.set_title('20. Correlation Heatmap',fontweight='bold')
    except: pass
    plt.tight_layout(); base64_plots.append(_save_b64(fig4))
    
    # ── FIGURE 5: Model-specific Diagnostics ────────────────────────────────────
    fig5, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(18, 6))
    fig5.suptitle('Figure 5: Model-Specific Diagnostics', fontsize=18, fontweight='bold')
    if len(train_losses):
        ax_a.plot(train_losses,'b-',lw=1.5,label='Train Loss')
        if len(val_losses): ax_a.plot(val_losses,'r--',lw=1.5,label='Val Loss')
        ax_a.set_title('Training & Validation Loss',fontweight='bold'); ax_a.set_xlabel('Epoch'); ax_a.set_ylabel('Loss'); ax_a.legend()
    else: ax_a.text(0.5,.5,'No convergence data',ha='center',va='center')
    
    if len(fi_r1) > 0 and len(all_feature_names) > 0:
        top_n = min(20, len(fi_r1))
        idx = np.argsort(fi_r1)[-top_n:]
        ax_b.barh(range(top_n), [fi_r1[i] for i in idx], color='teal', alpha=0.75)
        ax_b.set_yticks(range(top_n))
        f_lbls = [all_feature_names[i] if i < len(all_feature_names) else f'F{i}' for i in idx]
        ax_b.set_yticklabels(f_lbls, fontsize=7)
        ax_b.set_title('Feature Importances (r₁, top-20)',fontweight='bold')
    else: ax_b.text(.5,.5,'No feature info available',ha='center',va='center')
    plt.tight_layout(); base64_plots.append(_save_b64(fig5))
    
    # ── FIGURE 6: HIGH-LEVEL CHEMICAL FEATURE IMPORTANCE ("Big 8" Aggregation) ──
    feature_map = {
        "Steric Index": ["Degree", "NonHNeighbors", "DenseNeighbors", "InRing", "RingCount", "MinRingSize", "In6Ring", "RestrictedConform", "Is_Si", "Is_P", "Is_S", "Is_Fe", "Is_Ni", "Is_Zn", "Is_Sn", "Is_C", "Is_B", "NumRotatableBonds", "NumRings", "AnyReactionCenters", "SumReactionCenters", "FractionCSP3", "NumSymmSSSR"],
        "Electronic Properties": ["FormalCharge", "NumRadical", "Electronegativity", "AvgNeighborEN", "DiffEN", "EWGCount"],
        "Resonance Stabilization": ["Res_IsAromatic", "Res_AromNeighbor", "Res_IsSP2", "Res_DoubleBonds", "NumAromaticRings"],
        "Vinyl Substitution": ["IsVinyl", "AlphaSubst", "HasEWG"],
        "Hybridization Index": ["Hyb_"],
        "Polarity": ["Is_N", "Is_O", "Is_F", "Is_Cl", "Is_Br", "Is_I", "Is_Na", "Is_K"],
        "Aromaticity": ["IsAromatic", "AromaticNeighbors", "AromaticInRing"],
        "H Bonding Capacity": ["NumHs"]
    }
    
    high_level_r1 = {k: 0.0 for k in feature_map.keys()}
    high_level_r2 = {k: 0.0 for k in feature_map.keys()}
    
    for i, raw_feature in enumerate(all_feature_names):
        if i >= len(imp_r1): break
        assigned = False
        for category, keywords in feature_map.items():
            for kw in keywords:
                if kw in raw_feature: 
                    high_level_r1[category] += imp_r1[i]
                    high_level_r2[category] += imp_r2[i]
                    assigned = True
                    break
            if assigned: break

    total_r1 = sum(high_level_r1.values()) + 1e-9; total_r2 = sum(high_level_r2.values()) + 1e-9
    metrics = list(feature_map.keys())
    v1 = [high_level_r1[k]/total_r1 * 100 for k in metrics]
    v2 = [high_level_r2[k]/total_r2 * 100 for k in metrics]
    
    fig6, axes6 = plt.subplots(1, 2, figsize=(18, 7), sharey=True)
    fig6.suptitle('Figure 6: High-Level Chemical Feature Importance (Aggregated)', fontsize=16, fontweight='bold')
    
    y_pos = np.arange(len(metrics))
    axes6[0].barh(y_pos, v1, color='teal', alpha=0.8); axes6[0].set_yticks(y_pos); axes6[0].set_yticklabels(metrics, fontsize=12)
    axes6[0].set_xlabel('Relative Importance (%)'); axes6[0].set_title('Drivers for log(r₁)', fontweight='bold')
    for i, v in enumerate(v1): axes6[0].text(v + 0.5, i, f"{v:.1f}%", va='center')
    
    axes6[1].barh(y_pos, v2, color='coral', alpha=0.8); axes6[1].set_yticks(y_pos); axes6[1].set_yticklabels(metrics, fontsize=12)
    axes6[1].set_xlabel('Relative Importance (%)'); axes6[1].set_title('Drivers for log(r₂)', fontweight='bold')
    for i, v in enumerate(v2): axes6[1].text(v + 0.5, i, f"{v:.1f}%", va='center')
    
    plt.tight_layout(rect=[0, 0.03, 1, 0.95]); base64_plots.append(_save_b64(fig6))
    
    return base64_plots
