"use client";

import Link from "next/link";
import {
  Upload,
  Layers,
  Dumbbell,
  BarChart3,
  Beaker,
  GitCompare,
  Cpu,
  FlaskConical,
  FlaskRound,
  ArrowRight,
  Sparkles,
} from "lucide-react";

const PIPELINE_STEPS = [
  {
    icon: Upload,
    title: "Upload Data",
    desc: "Drop a CSV with monomer SMILES pairs and reactivity ratios. Auto-detect columns.",
    href: "/upload",
    color: "text-blue-400",
    step: "1",
  },
  {
    icon: Layers,
    title: "Feature Engineering",
    desc: "Morgan FP, RDKit descriptors, graph features, 3D autocorrelation, PCA, and more.",
    href: "/features",
    color: "text-purple-400",
    step: "2",
  },
  {
    icon: Dumbbell,
    title: "Train & Tune",
    desc: "27+ models with Grid/Random/Bayesian HP tuning and k-fold cross-validation.",
    href: "/training",
    color: "text-primary-400",
    step: "3",
  },
  {
    icon: BarChart3,
    title: "Results & Viz",
    desc: "Loss curves, scatter plots, residuals, R² tables, feature importance, and more.",
    href: "/results",
    color: "text-green-400",
    step: "4",
  },
];

const INFERENCE = [
  {
    icon: Beaker,
    title: "Predict",
    desc: "Run any model on a monomer pair to predict r₁ and r₂.",
    href: "/predict",
    color: "text-primary-400",
  },
  {
    icon: Cpu,
    title: "Model Catalog",
    desc: "Browse all 10 model architectures and details.",
    href: "/models",
    color: "text-purple-400",
  },
];

const STATS = [
  { label: "ML Models", value: "10" },
  { label: "Deep Learning", value: "7" },
  { label: "Traditional ML", value: "3" },
  { label: "Feature Methods", value: "6" },
  { label: "HP Tuning", value: "3" },
  { label: "Viz Types", value: "8+" },
];

export default function DashboardPage() {
  return (
    <div className="mx-auto max-w-6xl space-y-8">
      {/* Hero */}
      <div className="glass-card glow-blue relative overflow-hidden">
        <div className="absolute -right-20 -top-20 h-60 w-60 rounded-full bg-primary-600/10 blur-3xl" />
        <div className="relative space-y-4">
          <div className="flex items-center gap-2">
            <FlaskConical className="h-6 w-6 text-primary-400" />
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
            CopolPred
          </h1>
          <p className="max-w-2xl text-[var(--text-muted)]">
            Full ML experimentation platform for copolymerisation
            reactivity-ratio prediction. Upload datasets, engineer features,
            train <strong className="text-white">10 models</strong> with
            hyperparameter tuning, and visualise every metric — from loss curves
            to predicted vs actual scatter plots.
          </p>
          <div className="flex gap-3">
            <Link
              href="/upload"
              className="inline-flex items-center gap-2 rounded-lg bg-primary-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-primary-700"
            >
              Upload Dataset
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              href="/training"
              className="inline-flex items-center gap-2 rounded-lg border border-primary-400/30 bg-primary-600/10 px-5 py-2.5 text-sm font-medium text-primary-400 hover:bg-primary-600/20"
            >
              Train Models
            </Link>
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4 sm:grid-cols-6">
        {STATS.map((s) => (
          <div key={s.label} className="glass-card text-center">
            <p className="text-2xl font-bold text-white">{s.value}</p>
            <p className="text-xs text-[var(--text-muted)]">{s.label}</p>
          </div>
        ))}
      </div>

      {/* Pipeline steps */}
      <div>
        <h2 className="mb-4 text-lg font-semibold text-white">ML Pipeline</h2>
        <div className="grid gap-4 md:grid-cols-4">
          {PIPELINE_STEPS.map((s) => (
            <Link
              key={s.href}
              href={s.href}
              className="glass-card group relative"
            >
              <div className="absolute -top-2 -left-2 flex h-6 w-6 items-center justify-center rounded-full bg-primary-600 text-xs font-bold text-white">
                {s.step}
              </div>
              <s.icon className={`h-6 w-6 ${s.color}`} />
              <h3 className="mt-3 font-semibold text-white group-hover:text-primary-400">
                {s.title}
              </h3>
              <p className="mt-1 text-sm text-[var(--text-muted)]">{s.desc}</p>
            </Link>
          ))}
        </div>
      </div>

      {/* Inference cards */}
      <div>
        <h2 className="mb-4 text-lg font-semibold text-white">
          Quick Inference
        </h2>
        <div className="grid gap-4 md:grid-cols-4">
          {INFERENCE.map((f) => (
            <Link key={f.href} href={f.href} className="glass-card group">
              <f.icon className={`h-6 w-6 ${f.color}`} />
              <h3 className="mt-3 font-semibold text-white group-hover:text-primary-400">
                {f.title}
              </h3>
              <p className="mt-1 text-sm text-[var(--text-muted)]">{f.desc}</p>
            </Link>
          ))}
        </div>
      </div>

      {/* Model highlights */}
      <div className="glass-card">
        <div className="mb-4 flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-yellow-400" />
          <h2 className="font-semibold text-white">Model Highlights</h2>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {[
            {
              name: "Siamese MIMO",
              desc: "AE encoder → pair features → dual output",
              cat: "Deep Learning",
            },
            {
              name: "Bi-LSTM (Optimized)",
              desc: "2L×128h, Bayesian HP tuning, 20-fold CV",
              cat: "Deep Learning",
            },
            {
              name: "GAT MIMO",
              desc: "Multi-head graph attention on molecular graphs",
              cat: "Deep Learning",
            },
            {
              name: "Random Forest",
              desc: "200 trees on 248-dim graph-derived features",
              cat: "Traditional ML",
            },
            {
              name: "XGBoost",
              desc: "Gradient boosted trees, max_depth=5",
              cat: "Traditional ML",
            },
            {
              name: "GNN Custom",
              desc: "Custom graph neural net with message passing",
              cat: "Deep Learning",
            },
            {
              name: "Bayesian Ridge",
              desc: "Bayesian ridge regression with uncertainty",
              cat: "Traditional ML",
            },
            {
              name: "VAE",
              desc: "Variational AE with KL divergence",
              cat: "Generative",
            },
            {
              name: "Neural Net",
              desc: "4-layer feedforward with dropout",
              cat: "Deep Learning",
            },
          ].map((m) => (
            <div
              key={m.name}
              className="rounded-lg border border-[var(--border)] bg-[var(--bg)] p-3"
            >
              <p className="text-sm font-medium text-white">{m.name}</p>
              <p className="text-xs text-[var(--text-muted)]">{m.desc}</p>
              <span className="mt-1 inline-block text-[10px] text-primary-400">
                {m.cat}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
