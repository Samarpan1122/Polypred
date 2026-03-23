/* ──────────────────────────────────────────────────────────
   PolyPred — API client
   ────────────────────────────────────────────────────────── */

import type {
  PredictResponse,
  ModelInfo,
  CompareResponse,
  MoleculeInfo,
  DatasetInfo,
  DatasetPreview,
  DatasetStats,
  FeatureSetInfo,
  TrainRequest,
  TrainProgress,
  TrainResults,
  AvailableModel,
  ReactionValidateResponse,
  RankedModel,
} from "./types";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json() as Promise<T>;
}

// ─── Predict ──────────────────────────────────────────────
export async function predictSingle(
  smiles_a: string,
  smiles_b: string,
  model: string,
): Promise<PredictResponse> {
  return fetchJson("/api/predict/single", {
    method: "POST",
    body: JSON.stringify({ smiles_a, smiles_b, model }),
  });
}

export async function predictMulti(
  smiles_a: string,
  smiles_b: string,
  models: string[] = [],
): Promise<PredictResponse[]> {
  return fetchJson("/api/predict/multi", {
    method: "POST",
    body: JSON.stringify({ smiles_a, smiles_b, models }),
  });
}

export async function predictAll(
  smiles_a: string,
  smiles_b: string,
): Promise<PredictResponse[]> {
  return fetchJson("/api/predict/all", {
    method: "POST",
    body: JSON.stringify({ smiles_a, smiles_b, models: [] }),
  });
}

// ─── Models ───────────────────────────────────────────────
export async function listModels(): Promise<ModelInfo[]> {
  return fetchJson("/api/models/");
}

export async function listCategories(): Promise<Record<string, string[]>> {
  return fetchJson("/api/models/categories");
}

// ─── Compare ──────────────────────────────────────────────
export async function compareModels(
  smiles_a: string,
  smiles_b: string,
  models: string[] = [],
  category?: string,
): Promise<CompareResponse> {
  return fetchJson("/api/compare/", {
    method: "POST",
    body: JSON.stringify({ smiles_a, smiles_b, models, category }),
  });
}

// ─── Validate ─────────────────────────────────────────────
export async function validateMolecule(smiles: string): Promise<MoleculeInfo> {
  return fetchJson(
    `/api/predict/validate?smiles=${encodeURIComponent(smiles)}`,
    {
      method: "POST",
    },
  );
}

// ─── Datasets ─────────────────────────────────────────────
export async function uploadDataset(
  file: File,
  name?: string,
): Promise<DatasetInfo> {
  const formData = new FormData();
  formData.append("file", file);
  if (name) formData.append("name", name);
  const res = await fetch(`${API}/api/datasets/upload`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
  return res.json();
}

export async function listDatasets(): Promise<DatasetInfo[]> {
  return fetchJson("/api/datasets/");
}

export async function getDatasetPreview(
  id: string,
  rows = 50,
): Promise<DatasetPreview> {
  return fetchJson(`/api/datasets/${id}/preview?rows=${rows}`);
}

export async function getDatasetStats(id: string): Promise<DatasetStats> {
  return fetchJson(`/api/datasets/${id}/stats`);
}

export async function deleteDataset(id: string): Promise<void> {
  await fetchJson(`/api/datasets/${id}`, { method: "DELETE" });
}

// ─── Features ─────────────────────────────────────────────
export async function featurize(body: {
  dataset_id: string;
  smiles_col_a: string;
  smiles_col_b: string;
  method: string | string[];
  reduction?: string;
  reduction_params?: Record<string, number>;
}): Promise<FeatureSetInfo> {
  return fetchJson("/api/features/featurize", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function listFeatureSets(): Promise<FeatureSetInfo[]> {
  return fetchJson("/api/features/");
}

export async function getFeatureCorrelation(id: string, maxFeatures = 50) {
  return fetchJson<{ correlation_matrix: number[][]; feature_names: string[] }>(
    `/api/features/${id}/correlation?max_features=${maxFeatures}`,
  );
}

// ─── Training ─────────────────────────────────────────────
export async function startTraining(
  req: TrainRequest,
): Promise<{ job_id: string }> {
  return fetchJson("/api/training/start", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export async function getTrainProgress(jobId: string): Promise<TrainProgress> {
  return fetchJson(`/api/training/progress/${jobId}`);
}

export async function getTrainResults(jobId: string): Promise<TrainResults> {
  return fetchJson(`/api/training/results/${jobId}`);
}

export async function listTrainingJobs(): Promise<
  { job_id: string; status: string; message: string }[]
> {
  return fetchJson("/api/training/jobs");
}

export async function getAvailableModels(): Promise<
  Record<string, AvailableModel[]>
> {
  return fetchJson("/api/training/models/available");
}

// ─── Reaction Validator ───────────────────────────────────
export async function validateReaction(
  smiles_a: string,
  smiles_b: string,
): Promise<ReactionValidateResponse> {
  return fetchJson("/api/reaction/validate", {
    method: "POST",
    body: JSON.stringify({ smiles_a, smiles_b }),
  });
}

export async function getTopModels(): Promise<RankedModel[]> {
  return fetchJson("/api/reaction/top-models");
}
