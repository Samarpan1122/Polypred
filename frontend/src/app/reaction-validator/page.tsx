"use client";

import { useState, useEffect } from "react";
import MoleculeInput from "@/components/MoleculeInput";
import ResultsPanel from "@/components/ResultsPanel";
import { PredictionBarChart } from "@/components/Charts";
import {
  validateReaction,
  getTopModels,
  predictMulti,
  getAvailableModels,
} from "@/lib/api";
import type {
  ReactionValidateResponse,
  RankedModel,
  PredictResponse,
  AvailableModel,
} from "@/lib/types";
import {
  FlaskRound,
  CheckCircle2,
  AlertCircle,
  Play,
  Trophy,
  Loader2,
  ChevronDown,
  ChevronUp,
  Sparkles,
} from "lucide-react";

export default function ReactionValidatorPage() {
  // ── State ──
  const [smilesA, setSmilesA] = useState("");
  const [smilesB, setSmilesB] = useState("");
  const [validation, setValidation] = useState<ReactionValidateResponse | null>(
    null,
  );
  const [validating, setValidating] = useState(false);
  const [topModels, setTopModels] = useState<RankedModel[]>([]);
  const [allModels, setAllModels] = useState<
    Record<string, AvailableModel[]>
  >({});
  const [loadingModels, setLoadingModels] = useState(false);
  const [selectedModels, setSelectedModels] = useState<string[]>([]);
  const [results, setResults] = useState<PredictResponse[]>([]);
  const [predicting, setPredicting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAllModels, setShowAllModels] = useState(false);

  // Load available models catalog on mount
  useEffect(() => {
    getAvailableModels()
      .then(setAllModels)
      .catch(() => {});
  }, []);

  // ── Validate handler ──
  const handleValidate = async () => {
    if (!smilesA.trim() || !smilesB.trim()) return;
    setValidating(true);
    setError(null);
    setValidation(null);
    setTopModels([]);
    setResults([]);
    setSelectedModels([]);

    try {
      const res = await validateReaction(smilesA, smilesB);
      setValidation(res);

      // If both valid, fetch top models
      if (res.both_valid) {
        setLoadingModels(true);
        try {
          const models = await getTopModels();
          setTopModels(models);
          // Auto-select top 5 models
          setSelectedModels(models.slice(0, 5).map((m) => m.model_name));
        } catch {
          // No training results — that's fine
        } finally {
          setLoadingModels(false);
        }
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setValidating(false);
    }
  };

  // ── Predict handler ──
  const handlePredict = async () => {
    if (selectedModels.length === 0) return;
    setPredicting(true);
    setError(null);
    try {
      const res = await predictMulti(smilesA, smilesB, selectedModels);
      setResults(res);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setPredicting(false);
    }
  };

  // ── Model toggle ──
  const toggleModel = (name: string) => {
    setSelectedModels((prev) =>
      prev.includes(name) ? prev.filter((m) => m !== name) : [...prev, name],
    );
  };

  const selectAllTopModels = () => {
    setSelectedModels(topModels.map((m) => m.model_name));
  };

  const selectAllAvailableModels = () => {
    const allIds = Object.values(allModels)
      .flat()
      .filter(
        (m) =>
          !["autoencoder_standard", "autoencoder_denoising", "vae"].includes(
            m.id,
          ),
      )
      .map((m) => m.id);
    setSelectedModels(allIds);
  };

  const clearSelection = () => setSelectedModels([]);

  // ── Flatten all available model IDs ──
  const allModelIds = Object.values(allModels)
    .flat()
    .filter(
      (m) =>
        !["autoencoder_standard", "autoencoder_denoising", "vae"].includes(
          m.id,
        ),
    );

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3">
          <FlaskRound className="h-7 w-7 text-yellow-400" />
          <h1 className="text-2xl font-bold text-white">Reaction Validator</h1>
        </div>
        <p className="mt-1 text-sm text-[var(--text-muted)]">
          Validate two monomer SMILES, then find and run the best models for
          predicting r₁ and r₂ reactivity ratios.
        </p>
      </div>

      {/* ═══════════ Step 1: Input & Validate ═══════════ */}
      <div className="glass-card space-y-5">
        <div className="flex items-center gap-2">
          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary-600 text-xs font-bold text-white">
            1
          </span>
          <h2 className="font-semibold text-white">
            Enter &amp; Validate SMILES
          </h2>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-1">
            <MoleculeInput
              label="Monomer A (SMILES)"
              value={smilesA}
              onChange={(v) => {
                setSmilesA(v);
                setValidation(null);
              }}
              placeholder="e.g. C=Cc1ccccc1 (Styrene)"
              valid={validation ? validation.smiles_a.valid : null}
            />
            {validation && !validation.smiles_a.valid && (
              <p className="flex items-center gap-1 text-xs text-red-400">
                <AlertCircle className="h-3 w-3" />
                {validation.smiles_a.error}
              </p>
            )}
          </div>
          <div className="space-y-1">
            <MoleculeInput
              label="Monomer B (SMILES)"
              value={smilesB}
              onChange={(v) => {
                setSmilesB(v);
                setValidation(null);
              }}
              placeholder="e.g. C=C(C)C(=O)OC (MMA)"
              valid={validation ? validation.smiles_b.valid : null}
            />
            {validation && !validation.smiles_b.valid && (
              <p className="flex items-center gap-1 text-xs text-red-400">
                <AlertCircle className="h-3 w-3" />
                {validation.smiles_b.error}
              </p>
            )}
          </div>
        </div>

        <button
          onClick={handleValidate}
          disabled={!smilesA.trim() || !smilesB.trim() || validating}
          className="flex items-center gap-2 rounded-lg bg-primary-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-primary-700 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {validating ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <CheckCircle2 className="h-4 w-4" />
          )}
          Validate SMILES
        </button>

        {/* Validation result banner */}
        {validation && (
          <div
            className={`rounded-lg border p-4 ${
              validation.both_valid
                ? "border-green-500/30 bg-green-500/5"
                : "border-red-500/30 bg-red-500/5"
            }`}
          >
            <div className="flex items-center gap-2">
              {validation.both_valid ? (
                <>
                  <CheckCircle2 className="h-5 w-5 text-green-400" />
                  <span className="font-medium text-green-400">
                    Both SMILES are valid! Select models below to predict.
                  </span>
                </>
              ) : (
                <>
                  <AlertCircle className="h-5 w-5 text-red-400" />
                  <span className="font-medium text-red-400">
                    {!validation.smiles_a.valid && !validation.smiles_b.valid
                      ? "Both SMILES are invalid."
                      : !validation.smiles_a.valid
                        ? "Monomer A SMILES is invalid."
                        : "Monomer B SMILES is invalid."}
                  </span>
                </>
              )}
            </div>
          </div>
        )}

        {error && <p className="text-sm text-red-400">{error}</p>}
      </div>

      {/* ═══════════ Step 2: Model Selection ═══════════ */}
      {validation?.both_valid && (
        <div className="glass-card space-y-5">
          <div className="flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary-600 text-xs font-bold text-white">
              2
            </span>
            <h2 className="font-semibold text-white">Select Models</h2>
          </div>

          {/* Top models from training results */}
          {loadingModels ? (
            <div className="flex items-center gap-2 text-sm text-[var(--text-muted)]">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading trained models...
            </div>
          ) : topModels.length > 0 ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Trophy className="h-4 w-4 text-yellow-400" />
                  <span className="text-sm font-medium text-white">
                    Top Performing Models (from training)
                  </span>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={selectAllTopModels}
                    className="rounded-md border border-[var(--border)] px-2.5 py-1 text-xs text-[var(--text-muted)] hover:border-primary-500 hover:text-primary-400"
                  >
                    Select Top
                  </button>
                  <button
                    onClick={clearSelection}
                    className="rounded-md border border-[var(--border)] px-2.5 py-1 text-xs text-[var(--text-muted)] hover:border-red-500 hover:text-red-400"
                  >
                    Clear
                  </button>
                </div>
              </div>

              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {topModels.map((model, i) => {
                  const isSelected = selectedModels.includes(model.model_name);
                  return (
                    <button
                      key={`${model.model_name}-${model.job_id}`}
                      onClick={() => toggleModel(model.model_name)}
                      className={`group relative rounded-lg border p-3 text-left transition-all ${
                        isSelected
                          ? "border-primary-500/50 bg-primary-600/10"
                          : "border-[var(--border)] bg-[var(--bg)] hover:border-primary-500/30"
                      }`}
                    >
                      {i < 3 && (
                        <span className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full bg-yellow-500 text-[10px] font-bold text-black">
                          {i + 1}
                        </span>
                      )}
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium text-white">
                          {model.model_name.replace(/_/g, " ")}
                        </span>
                        <div
                          className={`h-3 w-3 rounded-full border ${
                            isSelected
                              ? "border-primary-500 bg-primary-500"
                              : "border-[var(--text-muted)]"
                          }`}
                        />
                      </div>
                      <div className="mt-1.5 flex gap-3 text-xs">
                        {model.r2_r1 !== null && (
                          <span className="text-[var(--text-muted)]">
                            R²(r₁):{" "}
                            <span className="text-white">
                              {model.r2_r1.toFixed(4)}
                            </span>
                          </span>
                        )}
                        {model.r2_r2 !== null && (
                          <span className="text-[var(--text-muted)]">
                            R²(r₂):{" "}
                            <span className="text-white">
                              {model.r2_r2.toFixed(4)}
                            </span>
                          </span>
                        )}
                      </div>
                      {model.avg_r2 !== null && (
                        <div className="mt-1">
                          <div className="h-1 w-full rounded-full bg-[var(--bg-hover)]">
                            <div
                              className="h-1 rounded-full bg-gradient-to-r from-primary-600 to-accent-500"
                              style={{
                                width: `${Math.max(0, Math.min(100, model.avg_r2 * 100))}%`,
                              }}
                            />
                          </div>
                          <span className="text-[10px] text-[var(--text-muted)]">
                            Avg R²: {model.avg_r2.toFixed(4)}
                          </span>
                        </div>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          ) : (
            <div className="rounded-lg border border-[var(--border)] bg-[var(--bg)] p-4 text-center">
              <p className="text-sm text-[var(--text-muted)]">
                No training results found. You can still select models from the
                catalog below to try predictions.
              </p>
            </div>
          )}

          {/* Try all models section */}
          <div className="border-t border-[var(--border)] pt-4">
            <button
              onClick={() => setShowAllModels(!showAllModels)}
              className="flex items-center gap-2 text-sm font-medium text-primary-400 hover:text-primary-300"
            >
              <Sparkles className="h-4 w-4" />
              Try All Available Models
              {showAllModels ? (
                <ChevronUp className="h-4 w-4" />
              ) : (
                <ChevronDown className="h-4 w-4" />
              )}
            </button>

            {showAllModels && (
              <div className="mt-3 space-y-3">
                <div className="flex gap-2">
                  <button
                    onClick={selectAllAvailableModels}
                    className="rounded-md border border-primary-500/30 bg-primary-600/10 px-3 py-1.5 text-xs font-medium text-primary-400 hover:bg-primary-600/20"
                  >
                    Select All Models
                  </button>
                  <button
                    onClick={clearSelection}
                    className="rounded-md border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--text-muted)] hover:border-red-500 hover:text-red-400"
                  >
                    Clear All
                  </button>
                </div>

                {Object.entries(allModels).map(([category, models]) => {
                  const filteredModels = models.filter(
                    (m) =>
                      ![
                        "autoencoder_standard",
                        "autoencoder_denoising",
                        "vae",
                      ].includes(m.id),
                  );
                  if (filteredModels.length === 0) return null;

                  return (
                    <div key={category}>
                      <p className="mb-2 text-xs font-medium uppercase tracking-wider text-[var(--text-muted)]">
                        {category.replace(/_/g, " ")}
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {filteredModels.map((model) => {
                          const isSelected = selectedModels.includes(model.id);
                          return (
                            <button
                              key={model.id}
                              onClick={() => toggleModel(model.id)}
                              className={`rounded-md border px-3 py-1.5 text-xs transition-all ${
                                isSelected
                                  ? "border-primary-500/50 bg-primary-600/15 text-primary-400"
                                  : "border-[var(--border)] text-[var(--text-muted)] hover:border-primary-500/30 hover:text-white"
                              }`}
                            >
                              {model.name}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Run button */}
          <button
            onClick={handlePredict}
            disabled={selectedModels.length === 0 || predicting}
            className="flex items-center gap-2 rounded-lg bg-accent-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-accent-700 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {predicting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Play className="h-4 w-4" />
            )}
            Run Prediction{selectedModels.length > 1 ? "s" : ""} (
            {selectedModels.length} model
            {selectedModels.length !== 1 ? "s" : ""})
          </button>
        </div>
      )}

      {/* ═══════════ Step 3: Results ═══════════ */}
      {(results.length > 0 || predicting) && (
        <div className="space-y-6">
          <div className="flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary-600 text-xs font-bold text-white">
              3
            </span>
            <h2 className="font-semibold text-white">Prediction Results</h2>
          </div>

          <ResultsPanel results={results} loading={predicting} />

          {results.length > 0 && <PredictionBarChart results={results} />}
        </div>
      )}
    </div>
  );
}
