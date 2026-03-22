"""Test training pipeline to find why scores are empty."""
import traceback
import numpy as np
from app.services.dataset_service import load_dataframe, split_dataset
from app.services.feature_service import featurize_dataset, load_feature_set
from app.models.schemas import (
    FeaturizationMethod, ModelType, TrainRequest, TrainProgress,
    SplitConfig, HPConfig, CVMethod, ModelResult,
)
from app.services.training_service import (
    _train_single_model, _prepare_fingerprints, DEVICE,
)

dataset_id = "73d99af2"
df = load_dataframe(dataset_id)
print(f"Dataset: {len(df)} rows, cols: {list(df.columns)}")

# Featurize
fs = featurize_dataset(dataset_id, "SMILES_A", "SMILES_B", FeaturizationMethod.MORGAN_FP)
print(f"Features: id={fs['id']}, n={fs['n_samples']}, dim={fs['n_features']}")
X, valid_idx, fs_meta = load_feature_set(fs["id"])

# Targets
Y = np.column_stack([
    df.loc[valid_idx, "r1"].values.astype(float),
    df.loc[valid_idx, "r2"].values.astype(float),
])
Y = np.nan_to_num(Y)
print(f"Y shape: {Y.shape}")

# Split
split = split_dataset(dataset_id, SplitConfig(method="random", test_size=0.2, val_size=0.1, random_state=42))
feat_map = {int(v): i for i, v in enumerate(valid_idx)}
tr_idx = [feat_map[j] for j in split["train_idx"] if j in feat_map]
te_idx = [feat_map[j] for j in split["test_idx"] if j in feat_map]
va_idx = [feat_map[j] for j in split.get("val_idx", []) if j in feat_map]

X_train, X_test = X[tr_idx], X[te_idx]
Y_train, Y_test = Y[tr_idx], Y[te_idx]
X_val = X[va_idx] if va_idx else None
Y_val = Y[va_idx] if va_idx else None
print(f"Train: {X_train.shape}, Test: {X_test.shape}")

# FPs for DL models
fp_data_raw = _prepare_fingerprints(df, valid_idx, "SMILES_A", "SMILES_B")
fp_data = None
if fp_data_raw is not None:
    fp_data = {
        "fps_a_train": fp_data_raw["fps_a"][tr_idx],
        "fps_b_train": fp_data_raw["fps_b"][tr_idx],
        "fps_a_test": fp_data_raw["fps_a"][te_idx],
        "fps_b_test": fp_data_raw["fps_b"][te_idx],
        "fps_a_all": fp_data_raw["fps_a"],
        "fps_b_all": fp_data_raw["fps_b"],
    }
    print(f"FP data ready: train={fp_data['fps_a_train'].shape}")
else:
    print("FP data is None!")

req = TrainRequest(
    dataset_id=dataset_id,
    smiles_col_a="SMILES_A",
    smiles_col_b="SMILES_B",
    target_cols=["r1", "r2"],
    models=[ModelType.LSTM_OPTIMIZED],
    epochs=2,
    batch_size=32,
    learning_rate=0.001,
)
progress = TrainProgress(job_id="test", status="running", total_models=1)

models = [
    ModelType.LSTM_OPTIMIZED,
    ModelType.SIAMESE_MIMO,
    ModelType.BASELINE_MLP_MIMO,
    ModelType.GAT_MIMO,
    ModelType.AUTOENCODER_STANDARD,
]

for mt in models:
    print(f"\n=== Testing {mt.value} ===")
    try:
        result = _train_single_model(
            mt, X_train, Y_train, X_test, Y_test,
            X_val, Y_val, req, progress, fp_data,
        )
        print(f"  r2_r1={result.r2_r1}, r2_r2={result.r2_r2}, time={result.training_time_s}s")
        if not result.r2_r1 and not result.training_time_s:
            print("  WARNING: Both r2_r1 and training_time are None!")
    except Exception as e:
        print(f"  EXCEPTION: {type(e).__name__}: {e}")
        traceback.print_exc()
