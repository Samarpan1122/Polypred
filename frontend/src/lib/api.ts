/* ──────────────────────────────────────────────────────────
   PolyPred - API client
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
  PublicShareRequestPayload,
  PublicShareRequestResponse,
  UserFilesResponse,
  PublicCatalogResponse,
  AdminOverviewResponse,
  AdminPublicShareRequestsResponse,
} from "./types";

const getApiBase = () => {
  if (process.env.NEXT_PUBLIC_API_URL) return process.env.NEXT_PUBLIC_API_URL;
  if (typeof window !== "undefined") {
    const isLocal =
      window.location.hostname === "localhost" ||
      window.location.hostname === "127.0.0.1";
    if (isLocal && window.location.port === "3000")
      return "http://localhost:8000";
  }
  return "";
};
const API = getApiBase();

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
  ownerId?: string,
  name?: string,
): Promise<DatasetInfo> {
  const formData = new FormData();
  formData.append("file", file);
  if (name) formData.append("name", name);
  if (ownerId) formData.append("owner_id", ownerId);
  const res = await fetch(`${API}/api/datasets/upload`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
  return res.json();
}

export async function listDatasets(ownerId?: string): Promise<DatasetInfo[]> {
  const suffix = ownerId ? `?owner_id=${encodeURIComponent(ownerId)}` : "";
  return fetchJson(`/api/datasets/${suffix}`);
}

export async function getDatasetPreview(
  id: string,
  ownerId?: string,
  rows = 50,
): Promise<DatasetPreview> {
  const owner = ownerId ? `&owner_id=${encodeURIComponent(ownerId)}` : "";
  return fetchJson(`/api/datasets/${id}/preview?rows=${rows}${owner}`);
}

export async function getDatasetStats(
  id: string,
  ownerId?: string,
): Promise<DatasetStats> {
  const owner = ownerId ? `?owner_id=${encodeURIComponent(ownerId)}` : "";
  return fetchJson(`/api/datasets/${id}/stats${owner}`);
}

export async function deleteDataset(
  id: string,
  ownerId?: string,
): Promise<void> {
  const owner = ownerId ? `?owner_id=${encodeURIComponent(ownerId)}` : "";
  await fetchJson(`/api/datasets/${id}${owner}`, { method: "DELETE" });
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

// ─── Public share requests ──────────────────────────────
export async function submitPublicShareRequest(
  payload: PublicShareRequestPayload,
): Promise<PublicShareRequestResponse> {
  return fetchJson("/api/public-share/requests", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getPublicCatalog(): Promise<PublicCatalogResponse> {
  return fetchJson("/api/public-share/catalog");
}

export async function getAdminOverview(
  adminEmail: string,
): Promise<AdminOverviewResponse> {
  return fetchJson(
    `/api/public-share/admin/overview?admin_email=${encodeURIComponent(adminEmail)}`,
  );
}

export async function listAdminPublicShareRequests(
  adminEmail: string,
  status: "all" | "pending_review" | "approved" | "rejected" = "all",
): Promise<AdminPublicShareRequestsResponse> {
  const query = new URLSearchParams({
    admin_email: adminEmail,
    status,
  });
  return fetchJson(`/api/public-share/admin/requests?${query.toString()}`);
}

export async function reviewPublicShareRequest(
  adminEmail: string,
  requestId: string,
  decision: "approved" | "rejected",
  reviewNotes = "",
): Promise<{ ok: boolean }> {
  return fetchJson(
    `/api/public-share/admin/requests/${encodeURIComponent(requestId)}/review?admin_email=${encodeURIComponent(adminEmail)}`,
    {
      method: "POST",
      body: JSON.stringify({
        decision,
        review_notes: reviewNotes,
      }),
    },
  );
}

// ─── Storage ───────────────────────────────────────────
export async function listUserFiles(
  ownerId: string,
  section: "all" | "datasets" | "models" | "results" | "requests" = "all",
  maxKeys = 120,
): Promise<UserFilesResponse> {
  const query = new URLSearchParams({
    owner_id: ownerId,
    section,
    max_keys: String(maxKeys),
  });
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 12000);
  try {
    return await fetchJson(`/api/storage/user-files?${query.toString()}`, {
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timer);
  }
}

export async function getUserDownloadUrl(
  ownerId: string,
  key: string,
  expiresIn = 300,
): Promise<{ ok: boolean; key: string; expires_in: number; url: string }> {
  const query = new URLSearchParams({
    owner_id: ownerId,
    key,
    expires_in: String(expiresIn),
  });
  return fetchJson(`/api/storage/download-url?${query.toString()}`);
}
