"use client";

import { useState } from "react";
import MoleculeInput from "@/components/MoleculeInput";
import ResultsPanel from "@/components/ResultsPanel";
import {
  PredictionBarChart,
  R1R2ScatterChart,
  LatencyChart,
} from "@/components/Charts";
import { compareModels } from "@/lib/api";
import type { PredictResponse, CompareResponse } from "@/lib/types";
import { GitCompare, Play } from "lucide-react";

const CATEGORIES = [
  { value: "", label: "All Models" },
  { value: "benchmark", label: "Benchmark Models" },
];

export default function ComparePage() {
  const [smilesA, setSmilesA] = useState("");
  const [smilesB, setSmilesB] = useState("");
  const [category, setCategory] = useState("");
  const [result, setResult] = useState<CompareResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCompare = async () => {
    if (!smilesA || !smilesB) return;
    setLoading(true);
    setError(null);
    try {
      const res = await compareModels(
        smilesA,
        smilesB,
        [],
        category || undefined,
      );
      setResult(res);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Compare Models</h1>
        <p className="text-sm text-[var(--text-muted)]">
          Run all models on the same input and compare predictions side-by-side
        </p>
      </div>

      {/* Input */}
      <div className="glass-card space-y-4">
        <div className="grid gap-4 md:grid-cols-2">
          <MoleculeInput
            label="Monomer A (SMILES)"
            value={smilesA}
            onChange={setSmilesA}
            placeholder="e.g. C=Cc1ccccc1 (Styrene)"
          />
          <MoleculeInput
            label="Monomer B (SMILES)"
            value={smilesB}
            onChange={setSmilesB}
            placeholder="e.g. C=C(C)C(=O)OC (MMA)"
          />
        </div>

        <div className="flex items-center gap-4">
          <div className="space-y-1">
            <label className="text-sm font-medium text-[var(--text)]">
              Category Filter
            </label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="smiles-input"
            >
              {CATEGORIES.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={handleCompare}
            disabled={!smilesA || !smilesB || loading}
            className="mt-6 flex items-center gap-2 rounded-lg bg-accent-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-accent-500 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <GitCompare className="h-4 w-4" />
            Compare All
          </button>
        </div>

        {error && <p className="text-sm text-red-400">{error}</p>}
      </div>

      {/* Summary Card */}
      {result && result.summary.num_models > 0 && (
        <div className="glass-card glow-green">
          <h3 className="mb-3 text-sm font-medium text-white">Summary</h3>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Stat label="Models" value={result.summary.num_models} />
            <Stat label="r₁ Mean" value={result.summary.r1_mean?.toFixed(4)} />
            <Stat label="r₂ Mean" value={result.summary.r2_mean?.toFixed(4)} />
            <Stat
              label="Avg Latency"
              value={`${result.summary.avg_latency_ms?.toFixed(1)} ms`}
            />
            <Stat
              label="r₁ Range"
              value={`${result.summary.r1_min?.toFixed(3)} – ${result.summary.r1_max?.toFixed(3)}`}
            />
            <Stat
              label="r₂ Range"
              value={`${result.summary.r2_min?.toFixed(3)} – ${result.summary.r2_max?.toFixed(3)}`}
            />
            <Stat
              label="Fastest"
              value={result.summary.fastest_model?.replace(/_/g, " ")}
            />
          </div>
        </div>
      )}

      {/* Results list */}
      {result && <ResultsPanel results={result.results} loading={loading} />}

      {/* Charts */}
      {result && result.results.length > 0 && (
        <div className="space-y-4">
          <PredictionBarChart results={result.results} />
          <div className="grid gap-4 lg:grid-cols-2">
            <R1R2ScatterChart results={result.results} />
            <LatencyChart results={result.results} />
          </div>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: any }) {
  return (
    <div>
      <p className="text-xs text-[var(--text-muted)]">{label}</p>
      <p className="text-sm font-semibold text-white">{value ?? "—"}</p>
    </div>
  );
}
