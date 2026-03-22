"use client";

import { useState, useEffect, useCallback } from "react";
import { Layers, Play, CheckCircle, RefreshCcw } from "lucide-react";
import { listDatasets, featurize, listFeatureSets } from "@/lib/api";
import type {
  DatasetInfo,
  FeaturizationMethod,
  FeatureReductionMethod,
  FeatureSetInfo,
} from "@/lib/types";

const FEAT_METHODS: { id: FeaturizationMethod; label: string; desc: string }[] =
  [
    {
      id: "morgan_fp",
      label: "Morgan Fingerprints",
      desc: "4096-bit circular fingerprints (concat for pair → 8192)",
    },
    {
      id: "flat_graph",
      label: "Flat Graph Features",
      desc: "58 node + 13 edge + 7 global → 248-dim per monomer",
    },
    {
      id: "rdkit_descriptors",
      label: "RDKit Descriptors",
      desc: "200+ physicochemical descriptors per molecule",
    },
    {
      id: "autocorr_3d",
      label: "3D Autocorrelation",
      desc: "160-dim 3D conformer-based descriptors",
    },
    {
      id: "combined_2d_3d",
      label: "Combined 2D+3D",
      desc: "RDKit descriptors + 3D autocorrelation combined",
    },
    {
      id: "all",
      label: "All Methods",
      desc: "Concatenate all featurization methods",
    },
  ];

const REDUCTION_METHODS: {
  id: FeatureReductionMethod;
  label: string;
  desc: string;
}[] = [
  { id: "none", label: "No Reduction", desc: "Use all features as-is" },
  {
    id: "pca",
    label: "PCA",
    desc: "Principal component analysis for dimensionality reduction",
  },
  {
    id: "correlation_filter",
    label: "Correlation Filter",
    desc: "Remove highly correlated features",
  },
  {
    id: "variance_threshold",
    label: "Variance Threshold",
    desc: "Remove low-variance features",
  },
  {
    id: "select_k_best",
    label: "SelectKBest",
    desc: "Select features by F-regression scores",
  },
];

export default function FeaturesPage() {
  const [datasets, setDatasets] = useState<DatasetInfo[]>([]);
  const [selectedDs, setSelectedDs] = useState<string>("");
  const [smilesA, setSmilesA] = useState("");
  const [smilesB, setSmilesB] = useState("");
  const [method, setMethod] = useState<FeaturizationMethod>("morgan_fp");
  const [reduction, setReduction] = useState<FeatureReductionMethod>("none");
  const [pcaComponents, setPcaComponents] = useState(50);
  const [corrThreshold, setCorrThreshold] = useState(0.95);
  const [kBest, setKBest] = useState(100);
  const [featureSets, setFeatureSets] = useState<FeatureSetInfo[]>([]);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<FeatureSetInfo | null>(null);
  const [error, setError] = useState("");

  const loadData = useCallback(async () => {
    const [ds, fs] = await Promise.all([listDatasets(), listFeatureSets()]);
    setDatasets(ds);
    setFeatureSets(fs);
    if (ds.length > 0 && !selectedDs) {
      setSelectedDs(ds[0].id);
      if (ds[0].smiles_columns.length >= 2) {
        setSmilesA(ds[0].smiles_columns[0]);
        setSmilesB(ds[0].smiles_columns[1]);
      }
    }
  }, [selectedDs]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const dsInfo = datasets.find((d) => d.id === selectedDs);

  const handleRun = async () => {
    if (!selectedDs || !smilesA || !smilesB) return;
    setRunning(true);
    setError("");
    setResult(null);
    try {
      const params: Record<string, number> = {};
      if (reduction === "pca") params.n_components = pcaComponents;
      if (reduction === "correlation_filter") params.threshold = corrThreshold;
      if (reduction === "select_k_best") params.k = kBest;

      const res = await featurize({
        dataset_id: selectedDs,
        smiles_col_a: smilesA,
        smiles_col_b: smilesB,
        method,
        reduction: reduction !== "none" ? reduction : undefined,
        reduction_params: Object.keys(params).length > 0 ? params : undefined,
      });
      setResult(res);
      await loadData();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Featurization failed");
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Feature Engineering</h1>
        <p className="text-sm text-[var(--text-muted)]">
          Convert SMILES to numerical features for ML models
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Left: Config */}
        <div className="space-y-5 lg:col-span-2">
          {/* Dataset + Columns */}
          <div className="glass-card rounded-xl p-5">
            <h2 className="mb-3 font-semibold text-white">Dataset & Columns</h2>
            <div className="grid gap-4 sm:grid-cols-3">
              <div>
                <label className="mb-1 block text-xs text-[var(--text-muted)]">
                  Dataset
                </label>
                <select
                  value={selectedDs}
                  onChange={(e) => {
                    setSelectedDs(e.target.value);
                    const ds = datasets.find((d) => d.id === e.target.value);
                    if (ds && ds.smiles_columns.length >= 2) {
                      setSmilesA(ds.smiles_columns[0]);
                      setSmilesB(ds.smiles_columns[1]);
                    }
                  }}
                  className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg-hover)] px-3 py-2 text-sm text-white"
                >
                  <option value="">Select...</option>
                  {datasets.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name} ({d.rows} rows)
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs text-[var(--text-muted)]">
                  SMILES Column A
                </label>
                <select
                  value={smilesA}
                  onChange={(e) => setSmilesA(e.target.value)}
                  className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg-hover)] px-3 py-2 text-sm text-white"
                >
                  <option value="">Select...</option>
                  {dsInfo?.columns.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs text-[var(--text-muted)]">
                  SMILES Column B
                </label>
                <select
                  value={smilesB}
                  onChange={(e) => setSmilesB(e.target.value)}
                  className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg-hover)] px-3 py-2 text-sm text-white"
                >
                  <option value="">Select...</option>
                  {dsInfo?.columns.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* Featurization method */}
          <div className="glass-card rounded-xl p-5">
            <h2 className="mb-3 font-semibold text-white">
              Featurization Method
            </h2>
            <div className="grid gap-2 sm:grid-cols-2">
              {FEAT_METHODS.map((m) => (
                <button
                  key={m.id}
                  onClick={() => setMethod(m.id)}
                  className={`rounded-lg border p-3 text-left transition-all ${
                    method === m.id
                      ? "border-primary-400 bg-primary-600/10"
                      : "border-[var(--border)] hover:border-primary-400/30"
                  }`}
                >
                  <div className="text-sm font-medium text-white">
                    {m.label}
                  </div>
                  <div className="mt-0.5 text-xs text-[var(--text-muted)]">
                    {m.desc}
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Reduction */}
          <div className="glass-card rounded-xl p-5">
            <h2 className="mb-3 font-semibold text-white">Feature Reduction</h2>
            <div className="grid gap-2 sm:grid-cols-3">
              {REDUCTION_METHODS.map((r) => (
                <button
                  key={r.id}
                  onClick={() => setReduction(r.id)}
                  className={`rounded-lg border p-3 text-left transition-all ${
                    reduction === r.id
                      ? "border-primary-400 bg-primary-600/10"
                      : "border-[var(--border)] hover:border-primary-400/30"
                  }`}
                >
                  <div className="text-sm font-medium text-white">
                    {r.label}
                  </div>
                  <div className="mt-0.5 text-xs text-[var(--text-muted)]">
                    {r.desc}
                  </div>
                </button>
              ))}
            </div>

            {/* Reduction params */}
            {reduction === "pca" && (
              <div className="mt-4">
                <label className="text-xs text-[var(--text-muted)]">
                  PCA Components: {pcaComponents}
                </label>
                <input
                  type="range"
                  min={10}
                  max={500}
                  value={pcaComponents}
                  onChange={(e) => setPcaComponents(Number(e.target.value))}
                  className="mt-1 w-full accent-primary-400"
                />
              </div>
            )}
            {reduction === "correlation_filter" && (
              <div className="mt-4">
                <label className="text-xs text-[var(--text-muted)]">
                  Correlation Threshold: {corrThreshold}
                </label>
                <input
                  type="range"
                  min={0.5}
                  max={0.99}
                  step={0.01}
                  value={corrThreshold}
                  onChange={(e) => setCorrThreshold(Number(e.target.value))}
                  className="mt-1 w-full accent-primary-400"
                />
              </div>
            )}
            {reduction === "select_k_best" && (
              <div className="mt-4">
                <label className="text-xs text-[var(--text-muted)]">
                  K Best Features: {kBest}
                </label>
                <input
                  type="range"
                  min={10}
                  max={500}
                  value={kBest}
                  onChange={(e) => setKBest(Number(e.target.value))}
                  className="mt-1 w-full accent-primary-400"
                />
              </div>
            )}
          </div>

          {/* Go button */}
          <button
            onClick={handleRun}
            disabled={running || !selectedDs}
            className="flex items-center gap-2 rounded-xl bg-primary-600 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-primary-500 disabled:opacity-40"
          >
            {running ? (
              <RefreshCcw className="h-4 w-4 animate-spin" />
            ) : (
              <Play className="h-4 w-4" />
            )}
            {running ? "Featurizing..." : "Run Featurization"}
          </button>

          {error && <p className="text-sm text-red-400">{error}</p>}

          {result && (
            <div className="glass-card flex items-center gap-3 rounded-xl p-4">
              <CheckCircle className="h-5 w-5 text-green-400" />
              <div>
                <p className="text-sm font-medium text-green-400">
                  Featurization Complete
                </p>
                <p className="text-xs text-[var(--text-muted)]">
                  {result.n_samples} samples × {result.n_features} features —
                  Method: {result.method}
                  {result.reduction !== "none" && ` + ${result.reduction}`}
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Right: Feature sets */}
        <div className="space-y-3">
          <h2 className="font-semibold text-white">Feature Sets</h2>
          {featureSets.length === 0 ? (
            <div className="glass-card rounded-xl p-4 text-center">
              <Layers className="mx-auto mb-2 h-8 w-8 text-[var(--text-muted)]" />
              <p className="text-sm text-[var(--text-muted)]">
                No feature sets yet
              </p>
            </div>
          ) : (
            featureSets.map((fs) => (
              <div key={fs.id} className="glass-card rounded-xl p-4">
                <div className="flex items-center gap-2">
                  <Layers className="h-4 w-4 text-primary-400" />
                  <span className="text-sm font-medium text-white capitalize">
                    {fs.method}
                  </span>
                </div>
                <div className="mt-1 flex flex-wrap gap-3 text-xs text-[var(--text-muted)]">
                  <span>{fs.n_samples} samples</span>
                  <span>{fs.n_features} features</span>
                </div>
                {fs.reduction !== "none" && (
                  <span className="mt-1 inline-block rounded-full bg-purple-500/10 px-2 py-0.5 text-[10px] text-purple-400">
                    Reduced: {fs.reduction}
                  </span>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
