"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import {
  BarChart3,
  TrendingUp,
  Table2,
  Download,
  RefreshCcw,
} from "lucide-react";
import { getTrainResults, listTrainingJobs } from "@/lib/api";
import type { TrainResults, ModelResult } from "@/lib/types";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  BarChart,
  Bar,
  Cell,
  ReferenceLine,
} from "recharts";

const COLORS = [
  "#3b82f6",
  "#22c55e",
  "#f59e0b",
  "#ef4444",
  "#a855f7",
  "#ec4899",
  "#06b6d4",
  "#84cc16",
  "#f97316",
  "#6366f1",
  "#14b8a6",
  "#e11d48",
  "#8b5cf6",
  "#0ea5e9",
];

function ResultsContent() {
  const searchParams = useSearchParams();
  const jobParam = searchParams.get("job");
  const [jobId, setJobId] = useState(jobParam || "");
  const [results, setResults] = useState<TrainResults | null>(null);
  const [jobs, setJobs] = useState<
    { job_id: string; status: string; message: string }[]
  >([]);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState<
    | "overview"
    | "scatter"
    | "loss"
    | "diagnostic_plots"
    | "comparison"
    | "importance"
    | "hp"
  >("overview");
  const [selectedModel, setSelectedModel] = useState<string>("");

  useEffect(() => {
    listTrainingJobs().then((j) =>
      setJobs(j.filter((x) => x.status === "completed")),
    );
  }, []);

  useEffect(() => {
    if (jobId) loadResults(jobId);
  }, [jobId]);

  const loadResults = async (id: string) => {
    setLoading(true);
    try {
      const r = await getTrainResults(id);
      setResults(r);
      if (r.results.length > 0) setSelectedModel(r.results[0].model_name);
    } catch {
      /* empty */
    } finally {
      setLoading(false);
    }
  };

  const model = results?.results.find((r) => r.model_name === selectedModel);

  const TABS = [
    { id: "overview" as const, label: "Scores Table", icon: Table2 },
    { id: "scatter" as const, label: "Pred vs Actual", icon: TrendingUp },
    { id: "loss" as const, label: "Loss Curves", icon: TrendingUp },
    {
      id: "diagnostic_plots" as const,
      label: "Diagnostic Plots",
      icon: BarChart3,
    },
    { id: "comparison" as const, label: "Model Comparison", icon: BarChart3 },
    { id: "importance" as const, label: "Feature Importance", icon: BarChart3 },
    { id: "hp" as const, label: "HP Results", icon: Table2 },
  ];

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">
            Results & Visualizations
          </h1>
          <p className="text-sm text-[var(--text-muted)]">
            Training metrics, plots, and model comparison
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={jobId}
            onChange={(e) => setJobId(e.target.value)}
            className="rounded-lg border border-[var(--border)] bg-[var(--bg-hover)] px-3 py-2 text-sm text-white"
          >
            <option value="">Select training job</option>
            {jobs.map((j) => (
              <option key={j.job_id} value={j.job_id}>
                Job {j.job_id} - {j.message?.slice(0, 40)}
              </option>
            ))}
          </select>
          {jobId && (
            <button
              onClick={() => loadResults(jobId)}
              className="rounded-lg bg-[var(--bg-hover)] p-2 text-[var(--text-muted)] hover:text-white"
            >
              <RefreshCcw
                className={`h-4 w-4 ${loading ? "animate-spin" : ""}`}
              />
            </button>
          )}
        </div>
      </div>

      {!results && !loading && (
        <div className="glass-card rounded-xl p-12 text-center">
          <BarChart3 className="mx-auto mb-3 h-12 w-12 text-[var(--text-muted)]" />
          <p className="text-[var(--text-muted)]">
            Select a completed training job to view results
          </p>
        </div>
      )}

      {results && (
        <>
          {/* Summary cards */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <SummaryCard
              label="Models Trained"
              value={results.summary.num_models}
            />
            <SummaryCard
              label="Best R² (r₁)"
              value={results.summary.best_r1_r2?.toFixed(4)}
              sub={results.summary.best_r1_model}
              color="text-blue-400"
            />
            <SummaryCard
              label="Best R² (r₂)"
              value={results.summary.best_r2_r2?.toFixed(4)}
              sub={results.summary.best_r2_model}
              color="text-green-400"
            />
            <SummaryCard
              label="Features"
              value={results.split_info.n_features}
              sub={`${results.split_info.train_size}/${results.split_info.val_size}/${results.split_info.test_size} split`}
            />
          </div>

          {/* Model selector */}
          <div className="flex flex-wrap gap-2">
            {results.results.map((r, i) => (
              <button
                key={`${r.model_name}-${i}`}
                onClick={() => setSelectedModel(r.model_name)}
                className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-all ${selectedModel === r.model_name
                    ? "border-primary-400 bg-primary-600/10 text-primary-400"
                    : "border-[var(--border)] text-[var(--text-muted)] hover:border-primary-400/30"
                  }`}
                style={
                  selectedModel === r.model_name
                    ? { borderColor: COLORS[i % COLORS.length] }
                    : {}
                }
              >
                {r.model_name.replace(/_/g, " ")}
              </button>
            ))}
          </div>

          {/* Tabs */}
          <div className="flex gap-1 rounded-xl bg-[var(--bg-card)] p-1">
            {TABS.map((t) => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-medium transition-all ${tab === t.id
                    ? "bg-primary-600/20 text-primary-400"
                    : "text-[var(--text-muted)] hover:text-white"
                  }`}
              >
                <t.icon className="h-3.5 w-3.5" />
                {t.label}
              </button>
            ))}
          </div>

          {/* Tab content */}
          <div className="glass-card rounded-xl p-5">
            {tab === "overview" && <ScoresTable results={results.results} />}
            {tab === "scatter" && model && <ScatterPlots model={model} />}
            {tab === "loss" && model && <LossCurves model={model} />}
            {tab === "diagnostic_plots" && model && (
              <DiagnosticPlots model={model} />
            )}
            {tab === "comparison" && (
              <ModelComparison results={results.results} />
            )}
            {tab === "importance" && model && (
              <FeatureImportance model={model} />
            )}
            {tab === "hp" && model && <HPResults model={model} />}
          </div>
        </>
      )}
    </div>
  );
}

export default function ResultsPage() {
  return (
    <Suspense fallback={<div className="text-white p-6">Loading...</div>}>
      <ResultsContent />
    </Suspense>
  );
}

// ─── Sub-components ─────────────────────────────────────
function SummaryCard({
  label,
  value,
  sub,
  color,
}: {
  label: string;
  value: unknown;
  sub?: string;
  color?: string;
}) {
  return (
    <div className="glass-card rounded-xl p-4">
      <p className="text-xs text-[var(--text-muted)]">{label}</p>
      <p className={`mt-1 text-2xl font-bold ${color || "text-white"}`}>
        {String(value ?? "-")}
      </p>
      {sub && <p className="mt-0.5 text-xs text-[var(--text-muted)]">{sub}</p>}
    </div>
  );
}

function ScoresTable({ results }: { results: ModelResult[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-xs">
        <thead>
          <tr className="border-b border-[var(--border)]">
            <th className="px-3 py-2 text-left text-[var(--text-muted)]">
              Model
            </th>
            <th className="px-3 py-2 text-right text-[var(--text-muted)]">
              R² (r₁)
            </th>
            <th className="px-3 py-2 text-right text-[var(--text-muted)]">
              R² (r₂)
            </th>
            <th className="px-3 py-2 text-right text-[var(--text-muted)]">
              MSE (r₁)
            </th>
            <th className="px-3 py-2 text-right text-[var(--text-muted)]">
              MSE (r₂)
            </th>
            <th className="px-3 py-2 text-right text-[var(--text-muted)]">
              MAE (r₁)
            </th>
            <th className="px-3 py-2 text-right text-[var(--text-muted)]">
              MAE (r₂)
            </th>
            <th className="px-3 py-2 text-right text-[var(--text-muted)]">
              RMSE (r₁)
            </th>
            <th className="px-3 py-2 text-right text-[var(--text-muted)]">
              RMSE (r₂)
            </th>
            <th className="px-3 py-2 text-right text-[var(--text-muted)]">
              CV R² (r₁)
            </th>
            <th className="px-3 py-2 text-right text-[var(--text-muted)]">
              CV R² (r₂)
            </th>
            <th className="px-3 py-2 text-right text-[var(--text-muted)]">
              Time
            </th>
          </tr>
        </thead>
        <tbody>
          {results.map((r, i) => (
            <tr
              key={`${r.model_name}-${i}`}
              className="border-b border-[var(--border)]/20 hover:bg-[var(--bg-hover)]"
            >
              <td className="px-3 py-2 font-medium text-white">
                {r.model_name.replace(/_/g, " ")}
              </td>
              <td className="px-3 py-2 text-right">{fmtMetric(r.r2_r1)}</td>
              <td className="px-3 py-2 text-right">{fmtMetric(r.r2_r2)}</td>
              <td className="px-3 py-2 text-right text-[var(--text-muted)]">
                {fmtMetric(r.mse_r1)}
              </td>
              <td className="px-3 py-2 text-right text-[var(--text-muted)]">
                {fmtMetric(r.mse_r2)}
              </td>
              <td className="px-3 py-2 text-right text-[var(--text-muted)]">
                {fmtMetric(r.mae_r1)}
              </td>
              <td className="px-3 py-2 text-right text-[var(--text-muted)]">
                {fmtMetric(r.mae_r2)}
              </td>
              <td className="px-3 py-2 text-right text-[var(--text-muted)]">
                {fmtMetric(r.rmse_r1)}
              </td>
              <td className="px-3 py-2 text-right text-[var(--text-muted)]">
                {fmtMetric(r.rmse_r2)}
              </td>
              <td className="px-3 py-2 text-right text-[var(--text-muted)]">
                {r.cv_r2_r1_mean != null
                  ? `${r.cv_r2_r1_mean.toFixed(3)}±${r.cv_r2_r1_std?.toFixed(3)}`
                  : "-"}
              </td>
              <td className="px-3 py-2 text-right text-[var(--text-muted)]">
                {r.cv_r2_r2_mean != null
                  ? `${r.cv_r2_r2_mean.toFixed(3)}±${r.cv_r2_r2_std?.toFixed(3)}`
                  : "-"}
              </td>
              <td className="px-3 py-2 text-right text-[var(--text-muted)]">
                {r.training_time_s?.toFixed(1)}s
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ScatterPlots({ model: m }: { model: ModelResult }) {
  const r1Data = m.y_true_r1.map((t, i) => ({
    actual: t,
    predicted: m.y_pred_r1[i],
  }));
  const r2Data = m.y_true_r2.map((t, i) => ({
    actual: t,
    predicted: m.y_pred_r2[i],
  }));
  const r1Range = getRange(r1Data);
  const r2Range = getRange(r2Data);
  const residualR1 = m.y_true_r1.map((t, i) => ({
    actual: t,
    residual: t - m.y_pred_r1[i],
  }));
  const residualR2 = m.y_true_r2.map((t, i) => ({
    actual: t,
    residual: t - m.y_pred_r2[i],
  }));

  return (
    <div className="space-y-6">
      <h3 className="text-sm font-semibold text-white">
        Predicted vs Actual - {m.model_name.replace(/_/g, " ")}
      </h3>
      <div className="grid gap-6 md:grid-cols-2">
        {/* r1 scatter */}
        {r1Data.length > 0 && (
          <div>
            <p className="mb-2 text-xs font-medium text-blue-400">
              r₁ (R² = {m.r2_r1?.toFixed(4)})
            </p>
            <ResponsiveContainer width="100%" height={300}>
              <ScatterChart>
                <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                <XAxis
                  dataKey="actual"
                  name="Actual"
                  tick={{ fontSize: 10, fill: "#888" }}
                  label={{
                    value: "Actual",
                    position: "bottom",
                    fill: "#888",
                    fontSize: 11,
                  }}
                />
                <YAxis
                  dataKey="predicted"
                  name="Predicted"
                  tick={{ fontSize: 10, fill: "#888" }}
                  label={{
                    value: "Predicted",
                    angle: -90,
                    position: "left",
                    fill: "#888",
                    fontSize: 11,
                  }}
                />
                <Tooltip
                  cursor={{ strokeDasharray: "3 3" }}
                  contentStyle={{
                    background: "#1a1a2e",
                    border: "1px solid #333",
                    borderRadius: 8,
                  }}
                />
                <ReferenceLine
                  segment={[
                    { x: r1Range[0], y: r1Range[0] },
                    { x: r1Range[1], y: r1Range[1] },
                  ]}
                  stroke="#555"
                  strokeDasharray="5 5"
                />
                <Scatter data={r1Data} fill="#3b82f6" fillOpacity={0.7} />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        )}
        {/* r2 scatter */}
        {r2Data.length > 0 && (
          <div>
            <p className="mb-2 text-xs font-medium text-green-400">
              r₂ (R² = {m.r2_r2?.toFixed(4)})
            </p>
            <ResponsiveContainer width="100%" height={300}>
              <ScatterChart>
                <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                <XAxis
                  dataKey="actual"
                  name="Actual"
                  tick={{ fontSize: 10, fill: "#888" }}
                  label={{
                    value: "Actual",
                    position: "bottom",
                    fill: "#888",
                    fontSize: 11,
                  }}
                />
                <YAxis
                  dataKey="predicted"
                  name="Predicted"
                  tick={{ fontSize: 10, fill: "#888" }}
                  label={{
                    value: "Predicted",
                    angle: -90,
                    position: "left",
                    fill: "#888",
                    fontSize: 11,
                  }}
                />
                <Tooltip
                  cursor={{ strokeDasharray: "3 3" }}
                  contentStyle={{
                    background: "#1a1a2e",
                    border: "1px solid #333",
                    borderRadius: 8,
                  }}
                />
                <ReferenceLine
                  segment={[
                    { x: r2Range[0], y: r2Range[0] },
                    { x: r2Range[1], y: r2Range[1] },
                  ]}
                  stroke="#555"
                  strokeDasharray="5 5"
                />
                <Scatter data={r2Data} fill="#22c55e" fillOpacity={0.7} />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Residual plots */}
      <h3 className="text-sm font-semibold text-white">Residual Plots</h3>
      <div className="grid gap-6 md:grid-cols-2">
        {residualR1.length > 0 && (
          <div>
            <p className="mb-2 text-xs font-medium text-blue-400">
              r₁ Residuals
            </p>
            <ResponsiveContainer width="100%" height={200}>
              <ScatterChart>
                <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                <XAxis dataKey="actual" tick={{ fontSize: 10, fill: "#888" }} />
                <YAxis
                  dataKey="residual"
                  tick={{ fontSize: 10, fill: "#888" }}
                />
                <Tooltip
                  contentStyle={{
                    background: "#1a1a2e",
                    border: "1px solid #333",
                    borderRadius: 8,
                  }}
                />
                <ReferenceLine y={0} stroke="#f59e0b" strokeDasharray="5 5" />
                <Scatter data={residualR1} fill="#3b82f6" fillOpacity={0.6} />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        )}
        {residualR2.length > 0 && (
          <div>
            <p className="mb-2 text-xs font-medium text-green-400">
              r₂ Residuals
            </p>
            <ResponsiveContainer width="100%" height={200}>
              <ScatterChart>
                <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                <XAxis dataKey="actual" tick={{ fontSize: 10, fill: "#888" }} />
                <YAxis
                  dataKey="residual"
                  tick={{ fontSize: 10, fill: "#888" }}
                />
                <Tooltip
                  contentStyle={{
                    background: "#1a1a2e",
                    border: "1px solid #333",
                    borderRadius: 8,
                  }}
                />
                <ReferenceLine y={0} stroke="#f59e0b" strokeDasharray="5 5" />
                <Scatter data={residualR2} fill="#22c55e" fillOpacity={0.6} />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  );
}

function LossCurves({ model: m }: { model: ModelResult }) {
  const lossData = m.train_loss_curve.map((tl, i) => ({
    epoch: i + 1,
    train_loss: tl,
    val_loss: m.val_loss_curve[i] ?? null,
  }));
  const r2Data = m.train_r2_curve.map((tr, i) => ({
    epoch: i + 1,
    r2_r1: tr,
    r2_r2: m.val_r2_curve[i] ?? null,
  }));

  if (lossData.length === 0) {
    return (
      <p className="text-sm text-[var(--text-muted)]">
        No loss curves available (traditional ML models don&apos;t have
        epoch-level loss)
      </p>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h3 className="mb-3 text-sm font-semibold text-white">
          Training & Validation Loss - {m.model_name.replace(/_/g, " ")}
        </h3>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={lossData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#333" />
            <XAxis
              dataKey="epoch"
              tick={{ fontSize: 10, fill: "#888" }}
              label={{
                value: "Epoch",
                position: "bottom",
                fill: "#888",
                fontSize: 11,
              }}
            />
            <YAxis
              tick={{ fontSize: 10, fill: "#888" }}
              label={{
                value: "Loss",
                angle: -90,
                position: "left",
                fill: "#888",
                fontSize: 11,
              }}
            />
            <Tooltip
              contentStyle={{
                background: "#1a1a2e",
                border: "1px solid #333",
                borderRadius: 8,
              }}
            />
            <Legend />
            <Line
              type="monotone"
              dataKey="train_loss"
              stroke="#3b82f6"
              dot={false}
              strokeWidth={2}
              name="Train Loss"
            />
            <Line
              type="monotone"
              dataKey="val_loss"
              stroke="#f59e0b"
              dot={false}
              strokeWidth={2}
              name="Val Loss"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {r2Data.length > 0 && (
        <div>
          <h3 className="mb-3 text-sm font-semibold text-white">
            R² Over Epochs
          </h3>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={r2Data}>
              <CartesianGrid strokeDasharray="3 3" stroke="#333" />
              <XAxis dataKey="epoch" tick={{ fontSize: 10, fill: "#888" }} />
              <YAxis tick={{ fontSize: 10, fill: "#888" }} domain={[-1, 1]} />
              <Tooltip
                contentStyle={{
                  background: "#1a1a2e",
                  border: "1px solid #333",
                  borderRadius: 8,
                }}
              />
              <Legend />
              <Line
                type="monotone"
                dataKey="r2_r1"
                stroke="#3b82f6"
                dot={false}
                strokeWidth={2}
                name="R² (r₁)"
              />
              <Line
                type="monotone"
                dataKey="r2_r2"
                stroke="#22c55e"
                dot={false}
                strokeWidth={2}
                name="R² (r₂)"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {m.best_epoch != null && (
        <p className="text-xs text-[var(--text-muted)]">
          Best epoch: {m.best_epoch + 1} (early stopping checkpoint)
        </p>
      )}
    </div>
  );
}

function ModelComparison({ results }: { results: ModelResult[] }) {
  const valid = results.filter((r) => r.r2_r1 != null);
  const barData = valid
    .map((r) => ({
      name: r.model_name.replace(/_/g, " ").slice(0, 15),
      r2_r1: r.r2_r1 ?? 0,
      r2_r2: r.r2_r2 ?? 0,
      mse_r1: r.mse_r1 ?? 0,
    }))
    .sort((a, b) => b.r2_r1 - a.r2_r1);

  return (
    <div className="space-y-6">
      <div>
        <h3 className="mb-3 text-sm font-semibold text-white">
          R² Score Comparison
        </h3>
        <ResponsiveContainer
          width="100%"
          height={Math.max(300, barData.length * 35)}
        >
          <BarChart data={barData} layout="vertical" margin={{ left: 100 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#333" />
            <XAxis
              type="number"
              tick={{ fontSize: 10, fill: "#888" }}
              domain={[0, 1]}
            />
            <YAxis
              dataKey="name"
              type="category"
              tick={{ fontSize: 10, fill: "#ccc" }}
              width={100}
            />
            <Tooltip
              contentStyle={{
                background: "#1a1a2e",
                border: "1px solid #333",
                borderRadius: 8,
              }}
            />
            <Legend />
            <Bar
              dataKey="r2_r1"
              fill="#3b82f6"
              name="R² (r₁)"
              barSize={14}
              radius={[0, 4, 4, 0]}
            />
            <Bar
              dataKey="r2_r2"
              fill="#22c55e"
              name="R² (r₂)"
              barSize={14}
              radius={[0, 4, 4, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div>
        <h3 className="mb-3 text-sm font-semibold text-white">
          MSE Comparison
        </h3>
        <ResponsiveContainer
          width="100%"
          height={Math.max(200, barData.length * 30)}
        >
          <BarChart
            data={barData.sort((a, b) => a.mse_r1 - b.mse_r1)}
            layout="vertical"
            margin={{ left: 100 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#333" />
            <XAxis type="number" tick={{ fontSize: 10, fill: "#888" }} />
            <YAxis
              dataKey="name"
              type="category"
              tick={{ fontSize: 10, fill: "#ccc" }}
              width={100}
            />
            <Tooltip
              contentStyle={{
                background: "#1a1a2e",
                border: "1px solid #333",
                borderRadius: 8,
              }}
            />
            <Bar
              dataKey="mse_r1"
              name="MSE (r₁)"
              barSize={14}
              radius={[0, 4, 4, 0]}
            >
              {barData.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Training time comparison */}
      <div>
        <h3 className="mb-3 text-sm font-semibold text-white">Training Time</h3>
        <ResponsiveContainer
          width="100%"
          height={Math.max(200, barData.length * 25)}
        >
          <BarChart
            data={valid
              .map((r) => ({
                name: r.model_name.replace(/_/g, " ").slice(0, 15),
                time: r.training_time_s ?? 0,
              }))
              .sort((a, b) => a.time - b.time)}
            layout="vertical"
            margin={{ left: 100 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#333" />
            <XAxis
              type="number"
              tick={{ fontSize: 10, fill: "#888" }}
              unit="s"
            />
            <YAxis
              dataKey="name"
              type="category"
              tick={{ fontSize: 10, fill: "#ccc" }}
              width={100}
            />
            <Tooltip
              contentStyle={{
                background: "#1a1a2e",
                border: "1px solid #333",
                borderRadius: 8,
              }}
            />
            <Bar
              dataKey="time"
              name="Seconds"
              fill="#a855f7"
              barSize={12}
              radius={[0, 4, 4, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function FeatureImportance({ model: m }: { model: ModelResult }) {
  const entries = Object.entries(m.feature_importance || {});
  if (entries.length === 0) {
    return (
      <p className="text-sm text-[var(--text-muted)]">
        Feature importance not available for this model type
      </p>
    );
  }
  const data = entries
    .sort((a, b) => b[1] - a[1])
    .slice(0, 20)
    .map(([name, val]) => ({ name, importance: val }));

  return (
    <div>
      <h3 className="mb-3 text-sm font-semibold text-white">
        Top-20 Feature Importance - {m.model_name.replace(/_/g, " ")}
      </h3>
      <ResponsiveContainer
        width="100%"
        height={Math.max(300, data.length * 28)}
      >
        <BarChart data={data} layout="vertical" margin={{ left: 60 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#333" />
          <XAxis type="number" tick={{ fontSize: 10, fill: "#888" }} />
          <YAxis
            dataKey="name"
            type="category"
            tick={{ fontSize: 10, fill: "#ccc" }}
            width={60}
          />
          <Tooltip
            contentStyle={{
              background: "#1a1a2e",
              border: "1px solid #333",
              borderRadius: 8,
            }}
          />
          <Bar
            dataKey="importance"
            fill="#f59e0b"
            barSize={14}
            radius={[0, 4, 4, 0]}
          >
            {data.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function HPResults({ model: m }: { model: ModelResult }) {
  if (!m.hp_search_results || m.hp_search_results.length === 0) {
    return (
      <p className="text-sm text-[var(--text-muted)]">
        No hyperparameter tuning results
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-white">
        HP Tuning Results - {m.model_name.replace(/_/g, " ")}
      </h3>
      {m.best_params && Object.keys(m.best_params).length > 0 && (
        <div className="rounded-lg bg-green-500/10 p-3">
          <p className="text-xs font-medium text-green-400">Best Parameters:</p>
          <pre className="mt-1 text-xs text-[var(--text-secondary)]">
            {JSON.stringify(m.best_params, null, 2)}
          </pre>
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="min-w-full text-xs">
          <thead>
            <tr className="border-b border-[var(--border)]">
              <th className="px-3 py-2 text-left text-[var(--text-muted)]">
                #
              </th>
              <th className="px-3 py-2 text-left text-[var(--text-muted)]">
                Parameters
              </th>
              <th className="px-3 py-2 text-right text-[var(--text-muted)]">
                Test Score
              </th>
              <th className="px-3 py-2 text-right text-[var(--text-muted)]">
                Train Score
              </th>
            </tr>
          </thead>
          <tbody>
            {m.hp_search_results.slice(0, 20).map((r, i) => (
              <tr key={i} className="border-b border-[var(--border)]/20">
                <td className="px-3 py-1.5 text-[var(--text-muted)]">
                  {i + 1}
                </td>
                <td className="px-3 py-1.5 font-mono text-[var(--text-secondary)]">
                  {Object.entries(r.params)
                    .map(([k, v]) => `${k}=${v}`)
                    .join(", ")}
                </td>
                <td className="px-3 py-1.5 text-right text-white">
                  {r.mean_test_score.toFixed(4)}
                </td>
                <td className="px-3 py-1.5 text-right text-[var(--text-muted)]">
                  {r.mean_train_score?.toFixed(4) ?? "-"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function DiagnosticPlots({ model: m }: { model: ModelResult }) {
  if (!m.diagnostic_plots || m.diagnostic_plots.length === 0) {
    return (
      <div className="flex h-40 items-center justify-center rounded-lg border border-dashed border-[var(--border)]">
        <p className="text-sm text-[var(--text-muted)]">
          No diagnostic plots available for this model.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h3 className="mb-3 text-sm font-semibold text-white">
        Comprehensive Diagnostic Suite & High-Level Chemical Importance
      </h3>
      <div className="grid grid-cols-1 gap-6">
        {m.diagnostic_plots.map((plotB64, idx) => (
          <div
            key={idx}
            className="flex items-center justify-center rounded-lg border border-[var(--border)] bg-white/5 p-4"
          >
            <img
              src={plotB64}
              alt={`Diagnostic Plot ${idx + 1}`}
              className="max-h-[600px] w-auto rounded-md shadow-sm"
              loading="lazy"
            />
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Helpers ──────────────────────────────────────────────
function fmtMetric(v: number | null | undefined): string {
  if (v == null) return "-";
  return v.toFixed(4);
}

function getRange(
  data: { actual: number; predicted: number }[],
): [number, number] {
  if (data.length === 0) return [0, 1];
  const all = data.flatMap((d) => [d.actual, d.predicted]);
  return [Math.min(...all), Math.max(...all)];
}
