"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import {
  Dumbbell,
  Play,
  ChevronDown,
  ChevronUp,
  RefreshCcw,
  CheckCircle,
  XCircle,
  Settings2,
} from "lucide-react";
import {
  listDatasets,
  listFeatureSets,
  getAvailableModels,
  startTraining,
  getTrainProgress,
} from "@/lib/api";
import type {
  DatasetInfo,
  FeatureSetInfo,
  FeaturizationMethod,
  HPTuningMethod,
  CVMethod,
  TrainProgress,
  TrainRequest,
  AvailableModel,
} from "@/lib/types";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/contexts/AuthContext";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

// Featurization is automated.

export default function TrainingPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const ownerId = user?.id || user?.email || "anonymous";

  useEffect(() => {
    if (!authLoading && !user) {
      router.push("/login");
    }
  }, [user, authLoading, router]);

  const [datasets, setDatasets] = useState<DatasetInfo[]>([]);
  const [featureSets, setFeatureSets] = useState<FeatureSetInfo[]>([]);
  const [availableModels, setAvailableModels] = useState<
    Record<string, AvailableModel[]>
  >({});
  const [selectedDs, setSelectedDs] = useState("");
  const [selectedFs, setSelectedFs] = useState("");
  const [smilesA, setSmilesA] = useState("");
  const [smilesB, setSmilesB] = useState("");
  const [targetCols, setTargetCols] = useState<string[]>([]);
  const [selectedModels, setSelectedModels] = useState<string[]>([
    "random_forest",
  ]);
  const [epochs, setEpochs] = useState(100);
  const [batchSize, setBatchSize] = useState(32);
  const [lr, setLr] = useState(0.001);
  const [testSize, setTestSize] = useState(0.2);
  const [valSize, setValSize] = useState(0.1);
  const [hpMethod, setHpMethod] = useState<HPTuningMethod>("none");
  const [hpIter, setHpIter] = useState(20);
  const [hpCvFolds, setHpCvFolds] = useState(5);
  const [cvMethod, setCvMethod] = useState<CVMethod>("none");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [progress, setProgress] = useState<TrainProgress | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const pollRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (!user?.email && !user?.id) return;
    (async () => {
      const [ds, fs, am] = await Promise.all([
        listDatasets(ownerId),
        listFeatureSets(),
        getAvailableModels(),
      ]);
      setDatasets(ds);
      setFeatureSets(fs);
      setAvailableModels(am);
      if (ds.length > 0) {
        setSelectedDs(ds[0].id);
        const d0 = ds[0];
        if (d0.smiles_columns.length >= 2) {
          setSmilesA(d0.smiles_columns[0]);
          setSmilesB(d0.smiles_columns[1]);
        } else {
          // Auto-detect from column names
          const cols = d0.columns;
          const sa =
            cols.find((c) => /smiles/i.test(c) && /[_a1]/i.test(c)) ??
            cols[0] ??
            "";
          const sb =
            cols.find((c) => /smiles/i.test(c) && /[_b2]/i.test(c)) ??
            cols[1] ??
            "";
          setSmilesA(sa);
          setSmilesB(sb);
        }
        if (d0.target_columns.length > 0) {
          setTargetCols(d0.target_columns.slice(0, 2));
        }
      }
    })();
  }, [ownerId, user?.email, user?.id]);

  const dsInfo = datasets.find((d) => d.id === selectedDs);

  const toggleModel = (id: string) => {
    setSelectedModels((prev) =>
      prev.includes(id) ? prev.filter((m) => m !== id) : [...prev, id],
    );
  };

  const selectCategory = (cat: string) => {
    const ids = (availableModels[cat] || []).map((m) => m.id);
    const allSelected = ids.every((id) => selectedModels.includes(id));
    if (allSelected) {
      setSelectedModels((prev) => prev.filter((m) => !ids.includes(m)));
    } else {
      setSelectedModels((prev) => [...new Set([...prev, ...ids])]);
    }
  };

  const handleTrain = async () => {
    if (!selectedDs || selectedModels.length === 0 || targetCols.length === 0)
      return;
    setRunning(true);
    setError("");
    setProgress(null);

    const req: TrainRequest = {
      user_id: ownerId,
      dataset_id: selectedDs,
      feature_set_id: selectedFs || undefined,
      featurization: ["all"] as FeaturizationMethod[],
      models: selectedModels,
      target_cols: targetCols,
      smiles_col_a: smilesA,
      smiles_col_b: smilesB,
      split: {
        method: "random",
        test_size: testSize,
        val_size: valSize,
        random_state: 42,
      },
      epochs,
      batch_size: batchSize,
      learning_rate: lr,
      hp_tuning: {
        method: hpMethod,
        n_iter: hpIter,
        cv_folds: hpCvFolds,
      },
      cv: cvMethod,
    };

    try {
      const { job_id } = await startTraining(req);
      // Poll progress
      pollRef.current = setInterval(async () => {
        try {
          const p = await getTrainProgress(job_id);
          setProgress(p);
          if (p.status === "completed" || p.status === "failed") {
            clearInterval(pollRef.current!);
            setRunning(false);
            if (p.status === "completed") {
              // Navigate to results after a brief delay
              setTimeout(() => router.push(`/results?job=${job_id}`), 1500);
            }
          }
        } catch {
          /* continue polling */
        }
      }, 1000);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Training failed");
      setRunning(false);
    }
  };

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  // Loss chart data
  const lossData =
    progress?.train_loss?.map((tl, i) => ({
      epoch: i + 1,
      train: tl,
      val: progress.val_loss?.[i] ?? null,
    })) || [];

  if (authLoading || !user) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <div className="text-white">Loading...</div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Train Models</h1>
        <p className="text-sm text-[var(--text-muted)]">
          Select models, configure hyperparameters, and train on your dataset
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Main config */}
        <div className="space-y-5 lg:col-span-2">
          {/* Dataset */}
          <div className="glass-card rounded-xl p-5">
            <h2 className="mb-3 font-semibold text-white">Dataset & Targets</h2>
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
                    if (ds) {
                      if (ds.smiles_columns.length >= 2) {
                        setSmilesA(ds.smiles_columns[0]);
                        setSmilesB(ds.smiles_columns[1]);
                      } else {
                        const cols = ds.columns;
                        const sa =
                          cols.find(
                            (c) => /smiles/i.test(c) && /[_a1]/i.test(c),
                          ) ??
                          cols[0] ??
                          "";
                        const sb =
                          cols.find(
                            (c) => /smiles/i.test(c) && /[_b2]/i.test(c),
                          ) ??
                          cols[1] ??
                          "";
                        setSmilesA(sa);
                        setSmilesB(sb);
                      }
                      if (ds.target_columns.length > 0) {
                        setTargetCols(ds.target_columns.slice(0, 2));
                      }
                    }
                  }}
                  className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg-hover)] px-3 py-2 text-sm text-white"
                >
                  {datasets.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs text-[var(--text-muted)]">
                  SMILES A
                </label>
                <select
                  value={smilesA}
                  onChange={(e) => setSmilesA(e.target.value)}
                  className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg-hover)] px-3 py-2 text-sm text-white"
                >
                  {dsInfo?.columns.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs text-[var(--text-muted)]">
                  SMILES B
                </label>
                <select
                  value={smilesB}
                  onChange={(e) => setSmilesB(e.target.value)}
                  className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg-hover)] px-3 py-2 text-sm text-white"
                >
                  {dsInfo?.columns.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs text-[var(--text-muted)]">
                  Targets
                </label>
                <div className="flex flex-wrap gap-1">
                  {dsInfo?.target_columns.map((c) => (
                    <button
                      key={c}
                      onClick={() =>
                        setTargetCols((prev) =>
                          prev.includes(c)
                            ? prev.filter((x) => x !== c)
                            : [...prev, c],
                        )
                      }
                      className={`rounded-full px-2 py-0.5 text-xs transition-colors ${
                        targetCols.includes(c)
                          ? "bg-green-500/20 text-green-400"
                          : "bg-[var(--bg-hover)] text-[var(--text-muted)]"
                      }`}
                    >
                      {c}
                    </button>
                  ))}
                  {dsInfo?.columns
                    .filter(
                      (c) =>
                        !dsInfo.smiles_columns.includes(c) &&
                        !dsInfo.target_columns.includes(c),
                    )
                    .slice(0, 5)
                    .map((c) => (
                      <button
                        key={c}
                        onClick={() =>
                          setTargetCols((prev) =>
                            prev.includes(c)
                              ? prev.filter((x) => x !== c)
                              : [...prev, c],
                          )
                        }
                        className={`rounded-full px-2 py-0.5 text-xs transition-colors ${
                          targetCols.includes(c)
                            ? "bg-green-500/20 text-green-400"
                            : "bg-[var(--bg-hover)] text-[var(--text-muted)]"
                        }`}
                      >
                        {c}
                      </button>
                    ))}
                </div>
              </div>
            </div>
          </div>

          {/* Feature set or method module removed natively */}

          {/* Model selection */}
          <div className="glass-card rounded-xl p-5">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="font-semibold text-white">
                Models ({selectedModels.length} selected)
              </h2>
              <div className="flex gap-2">
                <button
                  onClick={() =>
                    setSelectedModels(
                      Object.values(availableModels)
                        .flat()
                        .map((m) => m.id),
                    )
                  }
                  className="rounded bg-primary-600/20 px-2 py-1 text-[10px] text-primary-400 hover:bg-primary-600/30"
                >
                  Select All
                </button>
                <button
                  onClick={() => setSelectedModels([])}
                  className="rounded bg-[var(--bg-hover)] px-2 py-1 text-[10px] text-[var(--text-muted)] hover:text-white"
                >
                  Clear
                </button>
              </div>
            </div>

            {Object.entries(availableModels).map(([cat, models]) => (
              <div key={cat} className="mb-4">
                <button
                  onClick={() => selectCategory(cat)}
                  className="mb-2 text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] hover:text-white"
                >
                  {cat.replace(/_/g, " ")}
                </button>
                <div className="flex flex-wrap gap-2">
                  {models.map((m) => (
                    <button
                      key={m.id}
                      onClick={() => toggleModel(m.id)}
                      title={m.description}
                      className={`flex flex-col items-start rounded-lg border px-3 py-2 text-xs font-medium transition-all ${
                        selectedModels.includes(m.id)
                          ? "border-primary-400 bg-primary-600/10 text-primary-400"
                          : "border-[var(--border)] text-[var(--text-muted)] hover:border-primary-400/30 hover:text-white"
                      }`}
                    >
                      <span>{m.name}</span>
                      {m.estimated_time_seconds !== undefined && (
                        <span
                          className={`mt-0.5 text-[10px] ${selectedModels.includes(m.id) ? "text-primary-400/70" : "text-[var(--text-muted)]"}`}
                        >
                          ⏱ ~
                          {m.estimated_time_seconds < 60
                            ? `${m.estimated_time_seconds}s`
                            : `${Math.round(m.estimated_time_seconds / 60)}m`}
                        </span>
                      )}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>

          {/* Split config */}
          <div className="glass-card rounded-xl p-5">
            <h2 className="mb-3 font-semibold text-white">
              Train/Val/Test Split
            </h2>
            <div className="grid gap-4 sm:grid-cols-3">
              <div>
                <label className="text-xs text-[var(--text-muted)]">
                  Train: {((1 - testSize - valSize) * 100).toFixed(0)}%
                </label>
                <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-[var(--bg-hover)]">
                  <div
                    className="h-full rounded-full bg-blue-500"
                    style={{ width: `${(1 - testSize - valSize) * 100}%` }}
                  />
                </div>
              </div>
              <div>
                <label className="text-xs text-[var(--text-muted)]">
                  Val: {(valSize * 100).toFixed(0)}%
                </label>
                <input
                  type="range"
                  min={0}
                  max={0.3}
                  step={0.05}
                  value={valSize}
                  onChange={(e) => setValSize(Number(e.target.value))}
                  className="mt-1 w-full accent-primary-400"
                />
              </div>
              <div>
                <label className="text-xs text-[var(--text-muted)]">
                  Test: {(testSize * 100).toFixed(0)}%
                </label>
                <input
                  type="range"
                  min={0.1}
                  max={0.4}
                  step={0.05}
                  value={testSize}
                  onChange={(e) => setTestSize(Number(e.target.value))}
                  className="mt-1 w-full accent-primary-400"
                />
              </div>
            </div>
          </div>

          {/* Advanced Settings */}
          <button
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="flex items-center gap-2 text-sm text-[var(--text-muted)] hover:text-white"
          >
            <Settings2 className="h-4 w-4" />
            Advanced Settings
            {showAdvanced ? (
              <ChevronUp className="h-4 w-4" />
            ) : (
              <ChevronDown className="h-4 w-4" />
            )}
          </button>

          {showAdvanced && (
            <div className="glass-card space-y-4 rounded-xl p-5">
              {/* Training params */}
              <div className="grid gap-4 sm:grid-cols-3">
                <div>
                  <label className="mb-1 block text-xs text-[var(--text-muted)]">
                    Epochs
                  </label>
                  <input
                    type="number"
                    value={epochs}
                    onChange={(e) => setEpochs(Number(e.target.value))}
                    className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg-hover)] px-3 py-2 text-sm text-white"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-[var(--text-muted)]">
                    Batch Size
                  </label>
                  <select
                    value={batchSize}
                    onChange={(e) => setBatchSize(Number(e.target.value))}
                    className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg-hover)] px-3 py-2 text-sm text-white"
                  >
                    {[8, 16, 32, 64, 128, 256].map((b) => (
                      <option key={b} value={b}>
                        {b}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-xs text-[var(--text-muted)]">
                    Learning Rate
                  </label>
                  <select
                    value={lr}
                    onChange={(e) => setLr(Number(e.target.value))}
                    className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg-hover)] px-3 py-2 text-sm text-white"
                  >
                    {[0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05].map((v) => (
                      <option key={v} value={v}>
                        {v}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* HP Tuning */}
              <div>
                <h3 className="mb-2 text-sm font-semibold text-white">
                  Hyperparameter Tuning
                </h3>
                <div className="flex flex-wrap gap-2">
                  {(
                    [
                      "none",
                      "grid_search",
                      "random_search",
                      "bayesian_optimization",
                    ] as HPTuningMethod[]
                  ).map((m) => (
                    <button
                      key={m}
                      onClick={() => setHpMethod(m)}
                      className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-all ${
                        hpMethod === m
                          ? "border-primary-400 bg-primary-600/10 text-primary-400"
                          : "border-[var(--border)] text-[var(--text-muted)] hover:border-primary-400/30"
                      }`}
                    >
                      {m === "none"
                        ? "None"
                        : m
                            .replace(/_/g, " ")
                            .replace(/\b\w/g, (l) => l.toUpperCase())}
                    </button>
                  ))}
                </div>
                {hpMethod !== "none" && (
                  <div className="mt-3 grid gap-4 sm:grid-cols-2">
                    <div>
                      <label className="mb-1 block text-xs text-[var(--text-muted)]">
                        Iterations (Random/Bayesian)
                      </label>
                      <input
                        type="number"
                        value={hpIter}
                        onChange={(e) => setHpIter(Number(e.target.value))}
                        className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg-hover)] px-3 py-2 text-sm text-white"
                      />
                    </div>
                    <div>
                      <label className="mb-1 block text-xs text-[var(--text-muted)]">
                        CV Folds
                      </label>
                      <input
                        type="number"
                        value={hpCvFolds}
                        onChange={(e) => setHpCvFolds(Number(e.target.value))}
                        className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg-hover)] px-3 py-2 text-sm text-white"
                      />
                    </div>
                  </div>
                )}
              </div>

              {/* Cross-validation */}
              <div>
                <h3 className="mb-2 text-sm font-semibold text-white">
                  Cross-Validation
                </h3>
                <div className="flex flex-wrap gap-2">
                  {(
                    ["none", "kfold_5", "kfold_10", "kfold_20"] as CVMethod[]
                  ).map((m) => (
                    <button
                      key={m}
                      onClick={() => setCvMethod(m)}
                      className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-all ${
                        cvMethod === m
                          ? "border-primary-400 bg-primary-600/10 text-primary-400"
                          : "border-[var(--border)] text-[var(--text-muted)] hover:border-primary-400/30"
                      }`}
                    >
                      {m === "none"
                        ? "None"
                        : m.replace("kfold_", "").replace(/_/g, " ") + "-Fold"}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Train button */}
          <button
            onClick={handleTrain}
            disabled={running || !selectedDs || selectedModels.length === 0}
            className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-primary-600 to-purple-600 px-8 py-3.5 text-sm font-bold text-white shadow-lg transition-all hover:shadow-primary-600/30 disabled:opacity-40"
          >
            {running ? (
              <RefreshCcw className="h-5 w-5 animate-spin" />
            ) : (
              <Dumbbell className="h-5 w-5" />
            )}
            {running
              ? "Training..."
              : `Train ${selectedModels.length} Model${selectedModels.length === 1 ? "" : "s"}`}
          </button>

          {error && <p className="text-sm text-red-400">{error}</p>}
        </div>

        {/* Right: Progress */}
        <div className="space-y-4">
          <h2 className="font-semibold text-white">Training Progress</h2>

          {!progress && !running && (
            <div className="glass-card rounded-xl p-6 text-center">
              <Dumbbell className="mx-auto mb-2 h-8 w-8 text-[var(--text-muted)]" />
              <p className="text-sm text-[var(--text-muted)]">
                Configure and start training
              </p>
            </div>
          )}

          {progress && (
            <div className="glass-card space-y-4 rounded-xl p-5">
              {/* Status */}
              <div className="flex items-center gap-2">
                {progress.status === "completed" ? (
                  <CheckCircle className="h-5 w-5 text-green-400" />
                ) : progress.status === "failed" ? (
                  <XCircle className="h-5 w-5 text-red-400" />
                ) : (
                  <RefreshCcw className="h-5 w-5 animate-spin text-primary-400" />
                )}
                <span
                  className={`text-sm font-medium capitalize ${
                    progress.status === "completed"
                      ? "text-green-400"
                      : progress.status === "failed"
                        ? "text-red-400"
                        : "text-primary-400"
                  }`}
                >
                  {progress.status}
                </span>
              </div>

              {/* Message */}
              <p className="text-xs text-[var(--text-muted)]">
                {progress.message}
              </p>

              {/* Models progress bar */}
              <div>
                <div className="mb-1 flex justify-between text-xs text-[var(--text-muted)]">
                  <span>
                    Models: {progress.models_completed}/{progress.total_models}
                  </span>
                  {progress.current_model && (
                    <span className="text-primary-400">
                      {progress.current_model}
                    </span>
                  )}
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-[var(--bg-hover)]">
                  <div
                    className="h-full rounded-full bg-primary-500 transition-all"
                    style={{
                      width: `${(progress.models_completed / Math.max(progress.total_models, 1)) * 100}%`,
                    }}
                  />
                </div>
              </div>

              {/* Epoch progress */}
              {progress.total_epochs && progress.total_epochs > 0 && (
                <div>
                  <div className="mb-1 flex justify-between text-xs text-[var(--text-muted)]">
                    <span>
                      Epoch: {progress.current_epoch}/{progress.total_epochs}
                    </span>
                  </div>
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--bg-hover)]">
                    <div
                      className="h-full rounded-full bg-purple-500 transition-all"
                      style={{
                        width: `${((progress.current_epoch || 0) / progress.total_epochs) * 100}%`,
                      }}
                    />
                  </div>
                </div>
              )}

              {/* Stage progress for non-epoch workflows */}
              {progress.stage && progress.status === "running" && (
                <div>
                  <div className="mb-1 flex justify-between text-xs text-[var(--text-muted)]">
                    <span>Stage: {progress.stage.replace(/_/g, " ")}</span>
                    <span>
                      {Math.max(
                        0,
                        Math.min(100, Math.round(progress.stage_progress ?? 0)),
                      )}
                      %
                    </span>
                  </div>
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--bg-hover)]">
                    <div
                      className="h-full rounded-full bg-cyan-500 transition-all"
                      style={{
                        width: `${Math.max(0, Math.min(100, progress.stage_progress ?? 0))}%`,
                      }}
                    />
                  </div>
                </div>
              )}

              {/* Live loss chart */}
              {lossData.length > 2 && (
                <div>
                  <p className="mb-2 text-xs font-medium text-[var(--text-muted)]">
                    Loss Curve
                  </p>
                  <ResponsiveContainer width="100%" height={160}>
                    <LineChart data={lossData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                      <XAxis
                        dataKey="epoch"
                        tick={{ fontSize: 10, fill: "#888" }}
                      />
                      <YAxis tick={{ fontSize: 10, fill: "#888" }} />
                      <Tooltip
                        contentStyle={{
                          background: "#1a1a2e",
                          border: "1px solid #333",
                          borderRadius: 8,
                        }}
                        labelStyle={{ color: "#888" }}
                      />
                      <Line
                        type="monotone"
                        dataKey="train"
                        stroke="#3b82f6"
                        dot={false}
                        strokeWidth={2}
                        name="Train"
                      />
                      <Line
                        type="monotone"
                        dataKey="val"
                        stroke="#f59e0b"
                        dot={false}
                        strokeWidth={2}
                        name="Val"
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* Live activity panel for traditional ML where loss curves are not emitted */}
              {lossData.length <= 2 && progress.status === "running" && (
                <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-hover)]/40 p-3">
                  <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                    Live Activity
                  </p>
                  <p className="text-xs text-white/90">
                    {progress.message || "Working..."}
                  </p>
                  <p className="mt-1 text-[11px] text-[var(--text-muted)]">
                    Traditional models usually do not emit per-epoch loss
                    curves. Stage updates above are live.
                  </p>
                </div>
              )}

              {/* Elapsed time */}
              {progress.elapsed_seconds != null && (
                <p className="text-xs text-[var(--text-muted)]">
                  Elapsed:{" "}
                  {progress.elapsed_seconds > 0
                    ? `${progress.elapsed_seconds.toFixed(1)}s`
                    : "computing..."}
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
