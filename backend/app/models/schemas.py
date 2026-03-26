"""Pydantic schemas for the full PolyPred platform."""

from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field
from typing import Any


# ──────────────────────────────────────────────────────────
#  Enums
# ──────────────────────────────────────────────────────────
class FeaturizationMethod(str, Enum):
    # High-level "Big 8" chemical properties
    STERIC_INDEX = "steric_index"
    ELECTRONIC_PROPERTIES = "electronic_properties"
    RESONANCE_STABILIZATION = "resonance_stabilization"
    VINYL_SUBSTITUTION = "vinyl_substitution"
    HYBRIDIZATION_INDEX = "hybridization_index"
    POLARITY = "polarity"
    AROMATICITY = "aromaticity"
    H_BONDING_CAPACITY = "h_bonding_capacity"
    
    # Technical featurization methods
    MORGAN_FP = "morgan_fp"
    RDKIT_DESCRIPTORS = "rdkit_descriptors"
    GRAPH_FEATURES = "graph_features"
    FLAT_GRAPH = "flat_graph"
    AUTOCORR_3D = "autocorr_3d"
    COMBINED_2D_3D = "combined_2d_3d"
    
    ALL = "all"


class FeatureReductionMethod(str, Enum):
    NONE = "none"
    PCA = "pca"
    CORRELATION_FILTER = "correlation_filter"
    VARIANCE_THRESHOLD = "variance_threshold"
    MUTUAL_INFO = "mutual_info"
    SELECT_K_BEST = "select_k_best"


class ModelType(str, Enum):
    # Models from Specific_Models_Final (the only supported traininable models)
    # Siamese / Graph-based
    SIAMESE_LSTM = "siamese_lstm"
    SIAMESE_REGRESSION = "siamese_regression"
    SIAMESE_BAYESIAN = "siamese_bayesian"
    LSTM_SIAMESE_BAYESIAN = "lstm_siamese_bayesian"
    # LSTM-based
    LSTM_BAYESIAN = "lstm_bayesian"
    STANDALONE_LSTM = "standalone_lstm"
    # Traditional ML
    DECISION_TREE = "decision_tree"
    RANDOM_FOREST = "random_forest"
    ENSEMBLE_METHODS = "ensemble_methods"
    # Autoencoder
    AUTOENCODER = "autoencoder"


class HPTuningMethod(str, Enum):
    NONE = "none"
    GRID_SEARCH = "grid_search"
    RANDOM_SEARCH = "random_search"
    BAYESIAN_OPTIMIZATION = "bayesian_optimization"


class SplitMethod(str, Enum):
    RANDOM = "random"
    KFOLD = "kfold"
    STRATIFIED = "stratified"
    LEAVE_ONE_OUT = "leave_one_out"


class CVMethod(str, Enum):
    NONE = "none"
    KFOLD_5 = "kfold_5"
    KFOLD_10 = "kfold_10"
    KFOLD_20 = "kfold_20"
    KFOLD_100 = "kfold_100"
    LEAVE_ONE_MONOMER_OUT = "leave_one_monomer_out"


# ──────────────────────────────────────────────────────────
#  Request / Response Models
# ──────────────────────────────────────────────────────────
class DatasetInfo(BaseModel):
    id: str
    filename: str
    rows: int
    columns: list[str]
    smiles_col_a: str | None = None
    smiles_col_b: str | None = None
    target_cols: list[str] = []
    preview: list[dict[str, Any]] = []


class SplitConfig(BaseModel):
    method: SplitMethod = SplitMethod.RANDOM
    test_size: float = Field(0.2, ge=0.05, le=0.5)
    val_size: float = Field(0.1, ge=0.0, le=0.3)
    n_folds: int = Field(5, ge=2, le=100)
    random_seed: int = Field(42, alias="random_state")

    model_config = {"populate_by_name": True}


class FeaturizeRequest(BaseModel):
    dataset_id: str
    smiles_col_a: str
    smiles_col_b: str
    method: list[FeaturizationMethod] = Field(default_factory=lambda: [FeaturizationMethod.ALL])
    reduction: FeatureReductionMethod = FeatureReductionMethod.NONE
    reduction_params: dict[str, Any] | None = None


class FeaturizeResponse(BaseModel):
    feature_set_id: str
    method: list[str] | str
    reduction: str
    n_features: int
    n_samples: int
    feature_names: list[str] = []
    stats: dict[str, Any] = {}


class HPConfig(BaseModel):
    method: HPTuningMethod = HPTuningMethod.NONE
    param_grid: dict[str, list[Any]] = Field(default_factory=dict)
    n_iter: int = Field(50, ge=5, le=500)
    cv_folds: int = Field(5, ge=2, le=20)


class TrainSplit(BaseModel):
    test_size: float = 0.2
    val_size: float = 0.1
    random_seed: int = 42


class TrainHPTuning(BaseModel):
    method: HPTuningMethod = HPTuningMethod.NONE
    n_iter: int = 10
    cv_folds: int = 5


class TrainRequest(BaseModel):
    user_id: str | None = None
    dataset_id: str
    target_cols: list[str] = Field(default_factory=lambda: ["r1", "r2"])
    smiles_col_a: str = "SMILES_A"
    smiles_col_b: str = "SMILES_B"
    models: list[ModelType]

    # Featurization
    feature_set_id: str | None = None  # If provided, bypass featurization
    featurization: list[FeaturizationMethod] = Field(default_factory=lambda: [FeaturizationMethod.ALL])
    split: SplitConfig = Field(default_factory=SplitConfig)
    cv: CVMethod = CVMethod.NONE
    hp_tuning: HPConfig = Field(default_factory=HPConfig)
    epochs: int = Field(100, ge=1, le=1000)
    batch_size: int = Field(32, ge=4, le=512)
    learning_rate: float = Field(0.001, ge=1e-6, le=1.0)


class TrainProgress(BaseModel):
    job_id: str
    status: str  # queued, running, completed, failed
    current_model: str | None = None
    current_epoch: int = 0
    total_epochs: int = 0
    models_completed: int = 0
    total_models: int = 0
    train_loss: list[float] = []
    val_loss: list[float] = []
    train_r2: list[float] = []
    val_r2: list[float] = []
    elapsed_seconds: float = 0
    message: str = ""


class ModelResult(BaseModel):
    model_name: str
    model_type: str
    # Regression metrics
    r2_r1: float | None = None
    r2_r2: float | None = None
    mse_r1: float | None = None
    mse_r2: float | None = None
    mae_r1: float | None = None
    mae_r2: float | None = None
    rmse_r1: float | None = None
    rmse_r2: float | None = None
    # Log-space metrics
    r2_log_r1: float | None = None
    r2_log_r2: float | None = None
    medae_r1: float | None = None
    medae_r2: float | None = None
    max_error_r1: float | None = None
    max_error_r2: float | None = None
    mape_r1: float | None = None
    mape_r2: float | None = None
    evs_r1: float | None = None
    evs_r2: float | None = None
    pearson_r1: float | None = None
    pearson_r2: float | None = None
    # CV scores
    cv_r2_r1_mean: float | None = None
    cv_r2_r1_std: float | None = None
    cv_r2_r2_mean: float | None = None
    cv_r2_r2_std: float | None = None
    # Training info
    train_loss_curve: list[float] = []
    val_loss_curve: list[float] = []
    train_r2_curve: list[float] = []
    val_r2_curve: list[float] = []
    best_epoch: int | None = None
    training_time_s: float | None = None
    # HP tuning results
    best_params: dict[str, Any] = {}
    hp_search_results: list[dict[str, Any]] = []
    # Predictions
    y_true_r1: list[float] = []
    y_pred_r1: list[float] = []
    y_true_r2: list[float] = []
    y_pred_r2: list[float] = []
    # Feature importance
    feature_importance: dict[str, float] = {}
    # Visual Analytics
    diagnostic_plots: list[str] = []


class TrainResponse(BaseModel):
    job_id: str
    status: str
    results: list[ModelResult] = []
    summary: dict[str, Any] = {}
    split_info: dict[str, Any] = {}


class PredictRequest(BaseModel):
    smiles_a: str
    smiles_b: str
    model: str


class PredictMultiRequest(BaseModel):
    smiles_a: str
    smiles_b: str
    models: list[str] = Field(default_factory=list)


class PredictResponse(BaseModel):
    model: str
    r1: float | None = None
    r2: float | None = None
    latency_ms: float | None = None
    error: str | None = None
