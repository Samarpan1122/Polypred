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
    """Return the 10 trainable model types with exact hyperparameters from the IPYNBs.
    Dataset split: 80/20 train-test (random_state=42). All deep learning models use EPOCHS=100.
    """
    return {
        "traditional": [
            {
                "id": "decision_tree",
                "name": "Decision Tree",
                "description": (
                    "CART Decision Tree Regressor with RandomizedSearchCV + GridSearchCV tuning. "
                    "Hyperparams: max_depth (best from search, default 10), min_samples_split (best, default 5), "
                    "min_samples_leaf (best, default 2). "
                    "CV: KFold(n_splits=10, shuffle=True, random_state=42). "
                    "Split: test_size=0.2, random_state=42. "
                    "Input: flat graph features (248-dim). Outputs: r₁, r₂ (log scale)."
                ),
                "estimated_time_seconds": 30,
                "params": {
                    "max_depth": 10,
                    "min_samples_split": 5,
                    "min_samples_leaf": 2,
                    "cv_folds": 10,
                    "test_size": 0.2,
                    "tuning": "RandomizedSearchCV + GridSearchCV"
                }
            },
            {
                "id": "random_forest",
                "name": "Random Forest",
                "description": (
                    "Random Forest Regressor with GridSearchCV. "
                    "Grid: n_estimators=[100, 200], max_depth=[10, 20, None], min_samples_split=[2, 5]. "
                    "CV: GridSearchCV(cv=5, scoring=r2) + KFold(n_splits=10). "
                    "Split: test_size=0.2, random_state=42. n_jobs=-1. "
                    "Input: flat graph features (248-dim). Outputs: r₁, r₂ (log scale)."
                ),
                "estimated_time_seconds": 60,
                "params": {
                    "n_estimators": 200,
                    "max_depth": None,
                    "min_samples_split": 2,
                    "cv_folds": 10,
                    "test_size": 0.2,
                    "tuning": "GridSearchCV(cv=5)"
                }
            },
            {
                "id": "ensemble_methods",
                "name": "Ensemble Methods",
                "description": (
                    "Comparative benchmark of multiple sklearn ensembles. Best selected per target. "
                    "GradientBoosting: n_estimators=200, max_depth=4. "
                    "ExtraTrees: n_estimators=200. "
                    "XGBoost: n_estimators=200, max_depth=4, learning_rate=0.05, colsample_bytree=0.8. "
                    "CV: KFold(n_splits=10, shuffle=True, random_state=42). "
                    "Split: test_size=0.2, random_state=42. "
                    "Input: flat graph features (248-dim). Outputs: r₁, r₂ (log scale)."
                ),
                "estimated_time_seconds": 90,
                "params": {
                    "gradient_boosting": {"n_estimators": 200, "max_depth": 4},
                    "extra_trees": {"n_estimators": 200},
                    "xgboost": {"n_estimators": 200, "max_depth": 4, "learning_rate": 0.05},
                    "cv_folds": 10,
                    "test_size": 0.2
                }
            },
        ],
        "graph_based": [
            {
                "id": "siamese_lstm",
                "name": "Siamese + LSTM (PolyPredict)",
                "description": (
                    "Main PolyPredict model — 4-layer Siamese GAT + BiLSTM. "
                    "Architecture: SiameseGATArm with 4 GATConv layers (heads=4, dropout=0.1) + BN + residual skip, "
                    "GlobalAttention pooling (h=64, out=128); BiLSTM(input=128, hidden=lstm_h, num_layers=2) processes "
                    "graph embeddings as a 2-token sequence; FC regression head → (r₁, r₂). "
                    "Training: EPOCHS=100, batch=32, Adam(lr=1e-3, weight_decay=1e-4), "
                    "ReduceLROnPlateau(patience=5, factor=0.5). "
                    "Split: test_size=0.2, random_state=42. Input: molecular graphs (58 node × 13 edge × 7 global features)."
                ),
                "estimated_time_seconds": 600,
                "params": {
                    "gat_layers": 4,
                    "gat_heads": 4,
                    "gat_hidden": 64,
                    "gat_out": 128,
                    "gat_dropout": 0.1,
                    "lstm_layers": 2,
                    "epochs": 100,
                    "batch_size": 32,
                    "lr": 1e-3,
                    "weight_decay": 1e-4,
                    "scheduler": "ReduceLROnPlateau(patience=5, factor=0.5)",
                    "test_size": 0.2
                }
            },
            {
                "id": "siamese_regression",
                "name": "Siamese Regression",
                "description": (
                    "Siamese GNN with shared-weight 2-layer GAT arms. "
                    "Architecture: GATConv(in_ch, h, heads=4, dropout=0.2) → GATConv(h×4, out, heads=1, dropout=0.1); "
                    "|embedding_A - embedding_B| → FC regression head → (r₁, r₂). "
                    "Training: EPOCHS=100, batch=32, Adam(lr=1e-3, weight_decay=1e-4), "
                    "StepLR(step_size=10, gamma=0.5). "
                    "Split: test_size=0.2, random_state=42. Input: molecular graphs (58 node × 13 edge features)."
                ),
                "estimated_time_seconds": 300,
                "params": {
                    "gat_layers": 2,
                    "gat_heads_l1": 4,
                    "gat_heads_l2": 1,
                    "gat_dropout_l1": 0.2,
                    "gat_dropout_l2": 0.1,
                    "epochs": 100,
                    "batch_size": 32,
                    "lr": 1e-3,
                    "weight_decay": 1e-4,
                    "scheduler": "StepLR(step_size=10, gamma=0.5)",
                    "test_size": 0.2
                }
            },
            {
                "id": "siamese_bayesian",
                "name": "Siamese + Bayesian",
                "description": (
                    "Siamese GNN (same GAT architecture as Siamese Regression) with Bayesian hyperparameter optimization. "
                    "Architecture: GATConv(in_ch, h, heads=4, dropout=0.2) → GATConv(h×4, out, heads=1, dropout=0.1); "
                    "|emb_A - emb_B| → FC head → (r₁, r₂). "
                    "Hyperparams tuned via gp_minimize (scikit-optimize). "
                    "Training: EPOCHS=100, batch=32, Adam(lr=1e-3, weight_decay=1e-4), "
                    "StepLR(step_size=10, gamma=0.5). "
                    "Split: test_size=0.2, random_state=42. Input: molecular graphs (58 node × 13 edge features)."
                ),
                "estimated_time_seconds": 900,
                "params": {
                    "gat_layers": 2,
                    "gat_heads_l1": 4,
                    "gat_heads_l2": 1,
                    "gat_dropout_l1": 0.2,
                    "gat_dropout_l2": 0.1,
                    "epochs": 100,
                    "batch_size": 32,
                    "lr": 1e-3,
                    "weight_decay": 1e-4,
                    "scheduler": "StepLR(step_size=10, gamma=0.5)",
                    "tuning": "gp_minimize (Bayesian optimization)",
                    "test_size": 0.2
                }
            },
            {
                "id": "lstm_siamese_bayesian",
                "name": "LSTM + Siamese + Bayesian",
                "description": (
                    "Hybrid Siamese GAT + BiLSTM with Bayesian hyperparameter optimization. "
                    "Architecture: shared GATConv(node_dim, 64, heads=4, dropout=0.2) → GATConv(256, gnn_out=128); "
                    "BiLSTM(input=gnn_out, lstm_h=64, num_layers=2, bidirectional=True); "
                    "concat(hn) → FC head → (r₁, r₂). "
                    "Hyperparams tuned via gp_minimize. "
                    "Training: EPOCHS=100, batch=32, Adam(lr tuned by BO). "
                    "Split: test_size=0.2, random_state=42. Input: molecular graphs (58 node × 13 edge features)."
                ),
                "estimated_time_seconds": 1200,
                "params": {
                    "gat_layers": 2,
                    "gat_l1": "GATConv(node_dim, 64, heads=4, dropout=0.2)",
                    "gat_l2": "GATConv(256, 128, heads=1)",
                    "lstm_hidden": 64,
                    "lstm_layers": 2,
                    "epochs": 100,
                    "batch_size": 32,
                    "tuning": "gp_minimize (Bayesian optimization)",
                    "test_size": 0.2
                }
            },
        ],
        "lstm": [
            {
                "id": "lstm_bayesian",
                "name": "LSTM + Bayesian",
                "description": (
                    "Character-level SMILES BiLSTM with Bayesian-optimized hyperparameters. "
                    "Architecture: Embedding(vocab_size, emb_dim=64) → BiLSTM(hidden=128, num_layers=2, dropout=0.3, "
                    "bidirectional=True, batch_first=True) → Dropout(0.3) → FC head → (r₁, r₂). "
                    "Hyperparams (hidden, nlayers, dropout, lr) tuned via gp_minimize. "
                    "Training: EPOCHS=100, train_batch=32, test_batch=64, Adam(lr=3e-4, weight_decay=1e-5), "
                    "ReduceLROnPlateau(patience=5, factor=0.5). "
                    "Split: test_size=0.2, random_state=42. Input: SMILES char tokens (max_len=150)."
                ),
                "estimated_time_seconds": 600,
                "params": {
                    "emb_dim": 64,
                    "hidden": 128,
                    "num_layers": 2,
                    "dropout": 0.3,
                    "bidirectional": True,
                    "epochs": 100,
                    "batch_size": 32,
                    "lr": 3e-4,
                    "weight_decay": 1e-5,
                    "scheduler": "ReduceLROnPlateau(patience=5, factor=0.5)",
                    "tuning": "gp_minimize (Bayesian optimization)",
                    "max_len": 150,
                    "test_size": 0.2
                }
            },
            {
                "id": "standalone_lstm",
                "name": "Standalone LSTM",
                "description": (
                    "Character-level SMILES BiLSTM (no Bayesian tuning). "
                    "Architecture: Embedding(vocab_size, emb_dim=64) → BiLSTM(hidden=128, num_layers=2, dropout=0.3, "
                    "bidirectional=True, batch_first=True) → Dropout(0.3) → FC head → (r₁, r₂). "
                    "Training: EPOCHS=100, train_batch=32, test_batch=64, Adam(lr=3e-4, weight_decay=1e-5), "
                    "ReduceLROnPlateau(patience=5, factor=0.5). "
                    "Split: test_size=0.2, random_state=42. Input: SMILES char tokens (max_len=150)."
                ),
                "estimated_time_seconds": 300,
                "params": {
                    "emb_dim": 64,
                    "hidden": 128,
                    "num_layers": 2,
                    "dropout": 0.3,
                    "bidirectional": True,
                    "epochs": 100,
                    "batch_size": 32,
                    "lr": 3e-4,
                    "weight_decay": 1e-5,
                    "scheduler": "ReduceLROnPlateau(patience=5, factor=0.5)",
                    "max_len": 150,
                    "test_size": 0.2
                }
            },
        ],
        "autoencoder": [
            {
                "id": "autoencoder",
                "name": "VAE Autoencoder",
                "description": (
                    "Graph VAE (VGAE) with GCN encoder and joint regression head. "
                    "Architecture: GCNEncoder with GCNConv(in_ch, 128) → GCNConv(128, LATENT=32) "
                    "producing mu/logstd for reparameterization; global_mean_pool → latent z (32-dim); "
                    "pair latent [z_A; z_B; |z_A−z_B|] → FC regression head → (r₁, r₂). "
                    "KL divergence from VGAE encoder is added to reconstruction loss. "
                    "Training: EPOCHS=100, batch=32, Adam(lr=1e-3). "
                    "Split: test_size=0.2, random_state=42. Input: molecular graph (58 node features)."
                ),
                "estimated_time_seconds": 480,
                "params": {
                    "gcn_hidden": 128,
                    "latent_dim": 32,
                    "encoder": "GCNConv(in→128) → GCNConv(128→32) [mu, logstd]",
                    "epochs": 100,
                    "batch_size": 32,
                    "lr": 1e-3,
                    "loss": "MSE + KL divergence (VGAE)",
                    "test_size": 0.2
                }
            },
        ],
    }
