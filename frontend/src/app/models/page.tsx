"use client";

import { useEffect, useState } from "react";
import { listModels } from "@/lib/api";
import type { ModelInfo, ModelCategory } from "@/lib/types";
import { MODEL_CATEGORY_LABELS } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Cpu, Search } from "lucide-react";

const CATEGORY_COLORS: Record<string, string> = {
  deep_learning: "bg-blue-500/10 text-blue-400 border-blue-500/30",
  traditional_ml: "bg-green-500/10 text-green-400 border-green-500/30",
  encoder: "bg-purple-500/10 text-purple-400 border-purple-500/30",
  benchmark: "bg-amber-500/10 text-amber-400 border-amber-500/30",
};

// Static model descriptions (used when API isn't available)
const STATIC_MODELS: ModelInfo[] = [
  {
    name: "siamese_lstm",
    category: "benchmark",
    description: "Siamese GAT → BiLSTM → Explicit Difference Fusion → MLP (r₁, r₂)",
    input_type: "Molecular graph (58N + 7G features)",
    output_type: "(r₁, r₂)",
  },
  {
    name: "siamese_regression",
    category: "benchmark",
    description: "Siamese 2-layer GAT → concatenation → MLP regressor",
    input_type: "Molecular graph (58N features)",
    output_type: "(r₁, r₂)",
  },
  {
    name: "siamese_bayesian",
    category: "benchmark",
    description: "Siamese 2-layer GAT with Bayesian hyperparameter optimization",
    input_type: "Molecular graph (58N features)",
    output_type: "(r₁, r₂)",
  },
  {
    name: "lstm_bayesian",
    category: "benchmark",
    description: "BiLSTM over SMILES tokens with Bayesian HP tuning",
    input_type: "SMILES token sequences (vocab=30)",
    output_type: "(r₁, r₂)",
  },
  {
    name: "lstm_siamese_bayesian",
    category: "benchmark",
    description: "Siamese GAT → BiLSTM with Bayesian HP optimization",
    input_type: "Molecular graph (58N features)",
    output_type: "(r₁, r₂)",
  },
  {
    name: "standalone_lstm",
    category: "benchmark",
    description: "BiLSTM over SMILES token sequences → MLP head",
    input_type: "SMILES token sequences (vocab=30)",
    output_type: "(r₁, r₂)",
  },
  {
    name: "ensemble_methods",
    category: "benchmark",
    description: "Best Gradient Boosting ensemble from cross-validation",
    input_type: "Graph-derived flat features (130-dim)",
    output_type: "(r₁, r₂)",
  },
  {
    name: "decision_tree",
    category: "benchmark",
    description: "Decision Tree Regressor with optimal hyperparameter search",
    input_type: "Graph-derived flat features (130-dim)",
    output_type: "(r₁, r₂)",
  },
  {
    name: "random_forest",
    category: "benchmark",
    description: "Random Forest Regressor with optimal hyperparameter search",
    input_type: "Graph-derived flat features (130-dim)",
    output_type: "(r₁, r₂)",
  },
  {
    name: "autoencoder",
    category: "benchmark",
    description: "Variational Graph Autoencoder (VGAE) + MLP Regression Head",
    input_type: "Molecular graph (58N features)",
    output_type: "(r₁, r₂)",
  },
];

export default function ModelsPage() {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [search, setSearch] = useState("");
  const [filterCat, setFilterCat] = useState<string>("");

  useEffect(() => {
    listModels()
      .then(setModels)
      .catch(() => setModels(STATIC_MODELS));
  }, []);

  const filtered = models.filter((m) => {
    const matchSearch =
      !search ||
      m.name.toLowerCase().includes(search.toLowerCase()) ||
      m.description.toLowerCase().includes(search.toLowerCase());
    const matchCat = !filterCat || m.category === filterCat;
    return matchSearch && matchCat;
  });

  const categories = [...new Set(models.map((m) => m.category))];

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Model Catalog</h1>
        <p className="text-sm text-[var(--text-muted)]">
          All {models.length} models available in CopolPred
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--text-muted)]" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search models…"
            className="smiles-input w-full pl-10"
          />
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setFilterCat("")}
            className={cn(
              "rounded-lg border px-3 py-2 text-xs font-medium",
              !filterCat
                ? "border-primary-500 bg-primary-600/10 text-primary-400"
                : "border-[var(--border)] text-[var(--text-muted)] hover:text-white",
            )}
          >
            All
          </button>
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setFilterCat(cat === filterCat ? "" : cat)}
              className={cn(
                "rounded-lg border px-3 py-2 text-xs font-medium",
                cat === filterCat
                  ? CATEGORY_COLORS[cat]
                  : "border-[var(--border)] text-[var(--text-muted)] hover:text-white",
              )}
            >
              {MODEL_CATEGORY_LABELS[cat as ModelCategory] || cat}
            </button>
          ))}
        </div>
      </div>

      {/* Model grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {filtered.map((m) => (
          <div
            key={m.name}
            className="glass-card space-y-3 hover:border-primary-500/50"
          >
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-2">
                <Cpu className="h-4 w-4 text-[var(--text-muted)]" />
                <h3 className="text-sm font-semibold text-white">
                  {m.name.replace(/_/g, " ")}
                </h3>
              </div>
              <span
                className={cn(
                  "rounded-md border px-2 py-0.5 text-[10px] font-medium",
                  CATEGORY_COLORS[m.category] || "text-[var(--text-muted)]",
                )}
              >
                {MODEL_CATEGORY_LABELS[m.category as ModelCategory] ||
                  m.category}
              </span>
            </div>
            <p className="text-xs text-[var(--text-muted)]">{m.description}</p>
            <div className="space-y-1 border-t border-[var(--border)] pt-2">
              <div className="flex justify-between text-xs">
                <span className="text-[var(--text-muted)]">Input</span>
                <span className="text-[var(--text)]">{m.input_type}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-[var(--text-muted)]">Output</span>
                <span className="text-[var(--text)]">{m.output_type}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
