/* ──────────────────────────────────────────────────────────
   PolyPred - shared TypeScript types
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
  | "graph_based"
  | "lstm"
  | "autoencoder"
  | "siamese"
  | "generative"
  | "benchmark"
  | "unknown";

export const MODEL_CATEGORY_LABELS: Record<string, string> = {
  deep_learning: "Deep Learning",
  traditional_ml: "Traditional ML",
  traditional: "Traditional ML",
  graph_based: "Graph-Based (GNN)",
  lstm: "LSTM (Sequence)",
  autoencoder: "Autoencoder (VAE)",
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
  owner_id?: string;
  rows: number;
  cols: number;
  columns: string[];
  smiles_columns: string[];
  target_columns: string[];
  uploaded_at: string;
  is_public?: boolean;
  public_share_status?: string;
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

export type PublicShareAssetType = "dataset" | "model";

export interface PublicShareRequestPayload {
  asset_type: PublicShareAssetType;
  asset_id: string;
  asset_name: string;
  owner_id?: string;
  owner_email?: string;
  requester_name: string;
  institutional_email: string;
  affiliation: string;
  department?: string;
  position_title?: string;
  university_id?: string;
  orcid?: string;
  country: string;
  profile_url?: string;
  research_title: string;
  research_area: string;
  research_summary: string;
  intended_use: string;
  funding_source?: string;
  is_external_research_data: boolean;
  external_data_source?: string;
  external_data_license?: string;
  citation_text?: string;
  ethics_approval_required: boolean;
  ethics_approval_reference?: string;
  confirms_data_rights: boolean;
  confirms_no_pii: boolean;
  confirms_terms: boolean;
  additional_notes?: string;
}

export interface PublicShareRequestResponse {
  ok: boolean;
  request_id: string;
  status: string;
  message: string;
}

export interface PublicCatalogItem {
  request_id: string;
  asset_type: PublicShareAssetType;
  asset_id: string;
  asset_name: string;
  owner_id?: string;
  requester_name: string;
  affiliation: string;
  country: string;
  research_title: string;
  research_area: string;
  research_summary: string;
  intended_use: string;
  citation_text?: string;
  profile_url?: string;
  submitted_at: string;
  approved_at?: string | null;
}

export interface PublicCatalogResponse {
  ok: boolean;
  datasets: PublicCatalogItem[];
  models: PublicCatalogItem[];
  summary: {
    datasets: number;
    models: number;
    total: number;
  };
}

export interface PublicShareRequestRecord extends PublicShareRequestPayload {
  request_id: string;
  status: "pending_review" | "approved" | "rejected";
  submitted_at: string;
  reviewed_at?: string | null;
  reviewed_by?: string | null;
  review_notes?: string;
}

export interface AdminPublicShareRequestsResponse {
  ok: boolean;
  requests: PublicShareRequestRecord[];
  summary: {
    total: number;
    pending_review: number;
    approved: number;
    rejected: number;
  };
}

export interface AdminOverviewResponse {
  ok: boolean;
  admin_emails: string[];
  stats: {
    users: number;
    datasets: number;
    models: number;
    share_requests: number;
    pending_requests: number;
    approved_requests: number;
    rejected_requests: number;
    public_datasets: number;
    public_models: number;
  };
  recent_requests: Array<{
    request_id: string;
    asset_type: PublicShareAssetType;
    asset_id: string;
    asset_name: string;
    owner_id?: string;
    owner_email?: string;
    requester_name: string;
    institutional_email: string;
    affiliation: string;
    country: string;
    research_title: string;
    research_area: string;
    status: string;
    submitted_at: string;
    reviewed_at?: string | null;
    reviewed_by?: string | null;
    review_notes?: string;
  }>;
}

// ─── Feature types ──────────────────────────────────────
export type FeaturizationMethod =
  | "steric_index"
  | "electronic_properties"
  | "resonance_stabilization"
  | "vinyl_substitution"
  | "hybridization_index"
  | "polarity"
  | "aromaticity"
  | "h_bonding_capacity"
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
  user_id?: string;
  dataset_id: string;
  feature_set_id?: string;
  featurization: FeaturizationMethod[];
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
  stage?: string;
  stage_progress?: number;
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
  medae_r1?: number | null;
  medae_r2?: number | null;
  max_error_r1?: number | null;
  max_error_r2?: number | null;
  mape_r1?: number | null;
  mape_r2?: number | null;
  evs_r1?: number | null;
  evs_r2?: number | null;
  pearson_r1?: number | null;
  pearson_r2?: number | null;
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
  diagnostic_plots?: string[];
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

export interface StorageEncryptionPosture {
  mode: string;
  bucket_key_enabled: boolean;
}

export interface StorageFileItem {
  asset_id?: string;
  asset_type?: string;
  key: string;
  name: string;
  section: "datasets" | "models" | "results" | "requests";
  size: number;
  etag: string;
  last_modified?: string | null;
  storage_class: string;
  encryption: string;
  downloadable?: boolean;
  is_public?: boolean;
  public_share_status?: string;
}

export interface UserFilesResponse {
  ok: boolean;
  owner: string;
  section: "all" | "datasets" | "models" | "results" | "requests";
  count: number;
  encryption: StorageEncryptionPosture;
  files: StorageFileItem[];
  warnings?: string[];
}

export interface AvailableModel {
  id: string;
  name: string;
  description: string;
  estimated_time_seconds?: number;
  params?: Record<string, unknown>;
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
