/* ──────────────────────────────────────────────────────────
   PolyPred — shared TypeScript types
   ────────────────────────────────────────────────────────── */

// ─── Original predict types ─────────────────────────────
export interface PredictRequest {
  smiles_a: string;
  smiles_b: string;
  model: string;
}

export interface PredictMultiRequest {
  smiles_a: string;
  smiles_b: string;
  models: string[];
}

export interface PredictResponse {
  model: string;
  r1: number | null;
  r2: number | null;
  latency_ms: number | null;
  error: string | null;
}

export interface ModelInfo {
  name: string;
  category: string;
  description: string;
  input_type: string;
  output_type: string;
}

export interface CompareResponse {
  results: PredictResponse[];
  summary: {
    num_models: number;
    r1_mean?: number;
    r1_min?: number;
    r1_max?: number;
    r2_mean?: number;
    r2_min?: number;
    r2_max?: number;
    fastest_model?: string;
    avg_latency_ms?: number;
    error?: string;
  };
}

export interface MoleculeInfo {
  smiles: string;
  valid: boolean;
  descriptors: Record<string, number> | null;
  fingerprint_bits_set: number | null;
}

export type ModelCategory =
  | "deep_learning"
  | "traditional_ml"
  | "encoder"
  | "traditional"
  | "siamese"
  | "generative"
  | "benchmark"
  | "unknown";

export const MODEL_CATEGORY_LABELS: Record<string, string> = {
  deep_learning: "Deep Learning",
  traditional_ml: "Traditional ML",
  traditional: "Traditional ML",
  encoder: "Encoder / Autoencoder",
  siamese: "Siamese Networks",
  generative: "Generative Models",
  benchmark: "Benchmark Models",
  unknown: "Recently Trained Models",
};

export const MODEL_CATEGORY_COLORS: Record<string, string> = {
  deep_learning: "#3b82f6",
  traditional_ml: "#22c55e",
  traditional: "#22c55e",
  encoder: "#a855f7",
  siamese: "#f59e0b",
  generative: "#ec4899",
  benchmark: "#f97316",
  unknown: "#14b8a6",
};

// ─── Dataset types ──────────────────────────────────────
export interface DatasetInfo {
  id: string;
  name: string;
  rows: number;
  cols: number;
  columns: string[];
  smiles_columns: string[];
  target_columns: string[];
  uploaded_at: string;
}

export interface DatasetPreview {
  columns: string[];
  dtypes: Record<string, string>;
  rows: Record<string, unknown>[];
  shape: [number, number];
}

export interface DatasetStats {
  column_stats: Record<
    string,
    {
      mean: number;
      std: number;
      min: number;
      max: number;
      median: number;
      missing: number;
      dtype: string;
    }
  >;
  total_rows: number;
  total_cols: number;
}

// ─── Feature types ──────────────────────────────────────
export type FeaturizationMethod =
  | "morgan_fp"
  | "flat_graph"
  | "rdkit_descriptors"
  | "autocorr_3d"
  | "combined_2d_3d"
  | "graph_features"
  | "all";

export type FeatureReductionMethod =
  | "none"
  | "pca"
  | "correlation_filter"
  | "variance_threshold"
  | "select_k_best"
  | "mutual_info";

export interface FeatureSetInfo {
  id: string;
  dataset_id: string;
  method: string;
  reduction: string;
  n_samples: number;
  n_features: number;
  created_at: string;
}

// ─── Training types ─────────────────────────────────────
export type HPTuningMethod =
  | "none"
  | "grid_search"
  | "random_search"
  | "bayesian_optimization";
export type CVMethod =
  | "none"
  | "kfold_5"
  | "kfold_10"
  | "kfold_20"
  | "kfold_100"
  | "leave_one_monomer";

export interface TrainRequest {
  dataset_id: string;
  feature_set_id?: string;
  featurization: FeaturizationMethod;
  models: string[];
  target_cols: string[];
  smiles_col_a: string;
  smiles_col_b: string;
  split: {
    method: string;
    test_size: number;
    val_size: number;
    n_folds?: number;
    random_state: number;
  };
  epochs: number;
  batch_size: number;
  learning_rate: number;
  hp_tuning: {
    method: HPTuningMethod;
    n_iter: number;
    cv_folds: number;
    param_grid?: Record<string, unknown[]>;
  };
  cv: CVMethod;
}

export interface TrainProgress {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed";
  current_model?: string;
  models_completed: number;
  total_models: number;
  current_epoch?: number;
  total_epochs?: number;
  train_loss: number[];
  val_loss: number[];
  train_r2: number[];
  val_r2: number[];
  elapsed_seconds?: number;
  message?: string;
}

export interface ModelResult {
  model_name: string;
  model_type: string;
  r2_r1: number | null;
  r2_r2: number | null;
  mse_r1: number | null;
  mse_r2: number | null;
  mae_r1: number | null;
  mae_r2: number | null;
  rmse_r1: number | null;
  rmse_r2: number | null;
  cv_r2_r1_mean: number | null;
  cv_r2_r1_std: number | null;
  cv_r2_r2_mean: number | null;
  cv_r2_r2_std: number | null;
  y_true_r1: number[];
  y_pred_r1: number[];
  y_true_r2: number[];
  y_pred_r2: number[];
  train_loss_curve: number[];
  val_loss_curve: number[];
  train_r2_curve: number[];
  val_r2_curve: number[];
  feature_importance: Record<string, number>;
  training_time_s: number | null;
  best_params: Record<string, unknown>;
  best_epoch: number | null;
  hp_search_results: {
    params: Record<string, unknown>;
    mean_test_score: number;
    mean_train_score?: number;
  }[];
}

export interface TrainResults {
  job_id: string;
  split_info: {
    train_size: number;
    test_size: number;
    val_size: number;
    n_features: number;
  };
  results: ModelResult[];
  summary: {
    num_models: number;
    best_r1_model: string;
    best_r1_r2: number;
    best_r2_model: string;
    best_r2_r2: number;
    avg_r2_r1: number;
    avg_r2_r2: number;
  };
}

export interface AvailableModel {
  id: string;
  name: string;
  description: string;
}

// ─── Reaction Validator types ───────────────────────────
export interface SmilesValidation {
  smiles: string;
  valid: boolean;
  error: string | null;
}

export interface ReactionValidateResponse {
  smiles_a: SmilesValidation;
  smiles_b: SmilesValidation;
  both_valid: boolean;
}

export interface RankedModel {
  model_name: string;
  model_type: string;
  r2_r1: number | null;
  r2_r2: number | null;
  avg_r2: number | null;
  mse_r1: number | null;
  mse_r2: number | null;
  job_id: string | null;
}
