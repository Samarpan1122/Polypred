"use client";

import { useEffect, useState } from "react";
import { listModels } from "@/lib/api";
import type { ModelInfo, ModelCategory } from "@/lib/types";
import { MODEL_CATEGORY_LABELS } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Cpu, Search, X, ChevronLeft, ChevronRight } from "lucide-react";

const CATEGORY_COLORS: Record<string, string> = {
  deep_learning: "bg-blue-500/10 text-blue-400 border-blue-500/30",
  traditional_ml: "bg-green-500/10 text-green-400 border-green-500/30",
  encoder: "bg-purple-500/10 text-purple-400 border-purple-500/30",
  benchmark: "bg-amber-500/10 text-amber-400 border-amber-500/30",
};

const MODEL_IMAGES: Record<string, string[]> = {
  "decision_tree": ["image1.png", "image11.png", "image21.png", "image31.png"],
  "random_forest": ["image2.png", "image12.png", "image22.png", "image32.png"],
  "ensemble_methods": ["image3.png", "image13.png", "image23.png", "image33.png"],
  "siamese_regression": ["image4.png", "image14.png", "image24.png", "image34.png", "image41.png"],
  "standalone_lstm": ["image5.png", "image15.png", "image25.png", "image35.png", "image42.png"],
  "autoencoder": ["image6.png", "image16.png", "image26.png", "image36.png", "image43.png"],
  "siamese_lstm": ["image7.png", "image17.png", "image27.png", "image37.png", "image44.png"],
  "siamese_bayesian": ["image8.png", "image18.png", "image28.png", "image38.png", "image45.png"],
  "lstm_bayesian": ["image9.png", "image19.png", "image29.png", "image39.png", "image46.png"],
  "lstm_siamese_bayesian": ["image10.png", "image20.png", "image30.png", "image40.png", "image47.png"],
};

const SUPPLEMENTARY_IMAGES = [
  { src: "image48.png", caption: "Figure S48 - Chemical descriptor importance heatmap" },
  { src: "image49.png", caption: "Figure S49 - Average chemical descriptor importance" },
];

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
  const [lightbox, setLightbox] = useState<{ images: string[]; index: number } | null>(null);

  useEffect(() => {
    listModels()
      .then(setModels)
      .catch(() => setModels(STATIC_MODELS));
  }, []);

  // Close lightbox on Escape key
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (!lightbox) return;
      if (e.key === "Escape") setLightbox(null);
      if (e.key === "ArrowRight") setLightbox((p) => p ? { ...p, index: Math.min(p.index + 1, p.images.length - 1) } : null);
      if (e.key === "ArrowLeft") setLightbox((p) => p ? { ...p, index: Math.max(p.index - 1, 0) } : null);
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [lightbox]);

  const filtered = models.filter((m) => {
    const matchSearch =
      !search ||
      m.name.toLowerCase().includes(search.toLowerCase()) ||
      m.description.toLowerCase().includes(search.toLowerCase());
    const matchCat = !filterCat || m.category === filterCat;
    return matchSearch && matchCat;
  });

  const categories = [...new Set(models.map((m) => m.category))];

  const openLightbox = (images: string[], index: number) => {
    setLightbox({ images, index });
  };

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
        {filtered.map((m) => {
          const imgs = MODEL_IMAGES[m.name] || [];
          return (
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

              {imgs.length > 0 && (
                <div className="mt-4 border-t border-[var(--border)] pt-3">
                  <p className="mb-2 text-[10px] font-medium uppercase tracking-wider text-primary-400">
                    Supplementary Plots ({imgs.length})
                  </p>
                  <div className="grid grid-cols-3 gap-1.5">
                    {imgs.map((img, idx) => (
                      <button
                        key={img}
                        onClick={() => openLightbox(imgs.map(i => `/lstm_images/${i}`), idx)}
                        className="group relative overflow-hidden rounded border border-[var(--border)] bg-white/5 transition-all hover:border-primary-500/50 hover:shadow-lg hover:shadow-primary-500/10"
                      >
                        <img
                          src={`/lstm_images/${img}`}
                          alt={`${m.name} Figure S${img.replace("image", "").replace(".png", "")}`}
                          className="h-20 w-full object-contain transition-transform group-hover:scale-105"
                          loading="lazy"
                        />
                        <div className="absolute inset-0 flex items-center justify-center bg-black/0 transition-all group-hover:bg-black/40">
                          <span className="text-[10px] font-medium text-white opacity-0 transition-opacity group-hover:opacity-100">
                            Click to zoom
                          </span>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Supplementary cross-model figures */}
      <div className="glass-card">
        <h2 className="mb-4 text-lg font-semibold text-white">
          Supplementary - Cross-Model Analysis
        </h2>
        <div className="grid gap-4 sm:grid-cols-2">
          {SUPPLEMENTARY_IMAGES.map((s, idx) => (
            <button
              key={s.src}
              onClick={() => openLightbox(SUPPLEMENTARY_IMAGES.map(i => `/lstm_images/${i.src}`), idx)}
              className="group relative overflow-hidden rounded-lg border border-[var(--border)] bg-white/5 p-2 transition-all hover:border-primary-500/50"
            >
              <img
                src={`/lstm_images/${s.src}`}
                alt={s.caption}
                className="w-full rounded object-contain transition-transform group-hover:scale-[1.02]"
                loading="lazy"
              />
              <p className="mt-2 text-xs text-[var(--text-muted)]">{s.caption}</p>
              <div className="absolute inset-0 flex items-center justify-center rounded-lg bg-black/0 transition-all group-hover:bg-black/30">
                <span className="text-sm font-medium text-white opacity-0 transition-opacity group-hover:opacity-100">
                  Click to zoom
                </span>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Lightbox Modal */}
      {lightbox && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm"
          onClick={() => setLightbox(null)}
        >
          <div
            className="relative max-h-[90vh] max-w-[90vw]"
            onClick={(e) => e.stopPropagation()}
          >
            <img
              src={lightbox.images[lightbox.index]}
              alt="Zoomed plot"
              className="max-h-[85vh] max-w-[85vw] rounded-lg border border-[var(--border)] bg-white object-contain shadow-2xl"
            />
            {/* Close */}
            <button
              onClick={() => setLightbox(null)}
              className="absolute -right-3 -top-3 flex h-8 w-8 items-center justify-center rounded-full bg-red-600 text-white shadow-lg transition-transform hover:scale-110"
            >
              <X className="h-4 w-4" />
            </button>
            {/* Nav arrows */}
            {lightbox.index > 0 && (
              <button
                onClick={() => setLightbox({ ...lightbox, index: lightbox.index - 1 })}
                className="absolute left-2 top-1/2 -translate-y-1/2 flex h-10 w-10 items-center justify-center rounded-full bg-black/60 text-white transition-all hover:bg-black/80"
              >
                <ChevronLeft className="h-6 w-6" />
              </button>
            )}
            {lightbox.index < lightbox.images.length - 1 && (
              <button
                onClick={() => setLightbox({ ...lightbox, index: lightbox.index + 1 })}
                className="absolute right-2 top-1/2 -translate-y-1/2 flex h-10 w-10 items-center justify-center rounded-full bg-black/60 text-white transition-all hover:bg-black/80"
              >
                <ChevronRight className="h-6 w-6" />
              </button>
            )}
            {/* Counter */}
            <div className="absolute bottom-3 left-1/2 -translate-x-1/2 rounded-full bg-black/60 px-3 py-1 text-xs text-white">
              {lightbox.index + 1} / {lightbox.images.length}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
