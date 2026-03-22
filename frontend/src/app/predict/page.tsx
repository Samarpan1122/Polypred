"use client";

import { useState, useEffect } from "react";
import MoleculeInput from "@/components/MoleculeInput";
import ModelSelector from "@/components/ModelSelector";
import ResultsPanel from "@/components/ResultsPanel";
import { PredictionBarChart } from "@/components/Charts";
import { listModels, predictMulti, validateMolecule } from "@/lib/api";
import type { PredictResponse, ModelInfo } from "@/lib/types";
import { Play, Upload } from "lucide-react";
import { cn } from "@/lib/utils";

export default function PredictPage() {
  const [mode, setMode] = useState<"single" | "batch">("single");
  
  // Single mode state
  const [smilesA, setSmilesA] = useState("");
  const [smilesB, setSmilesB] = useState("");
  const [validA, setValidA] = useState<boolean | null>(null);
  const [validB, setValidB] = useState<boolean | null>(null);
  const [results, setResults] = useState<PredictResponse[]>([]);
  
  // Batch mode state
  const [batchFile, setBatchFile] = useState<File | null>(null);
  const [batchRows, setBatchRows] = useState<{a: string, b: string}[]>([]);
  const [batchResults, setBatchResults] = useState<{a: string, b: string, res: PredictResponse[]}[]>([]);

  // Common state
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Debounced SMILES validation
  useEffect(() => {
    if (!smilesA) { setValidA(null); return; }
    const timer = setTimeout(() => {
      validateMolecule(smilesA)
        .then((info) => setValidA(info.valid))
        .catch(() => setValidA(null));
    }, 400);
    return () => clearTimeout(timer);
  }, [smilesA]);

  useEffect(() => {
    if (!smilesB) { setValidB(null); return; }
    const timer = setTimeout(() => {
      validateMolecule(smilesB)
        .then((info) => setValidB(info.valid))
        .catch(() => setValidB(null));
    }, 400);
    return () => clearTimeout(timer);
  }, [smilesB]);

  useEffect(() => {
    listModels()
      .then((m) => {
        setModels(m);
        // Default: select all non-encoder models
        setSelected(
          m.filter((x) => x.category !== "encoder").map((x) => x.name),
        );
      })
      .catch(() => {
        // API not available — show placeholder models
        const placeholders: ModelInfo[] = [
          {
            name: "siamese_lstm",
            category: "benchmark",
            description: "",
            input_type: "",
            output_type: "",
          },
          {
            name: "siamese_regression",
            category: "benchmark",
            description: "",
            input_type: "",
            output_type: "",
          },
          {
            name: "siamese_bayesian",
            category: "benchmark",
            description: "",
            input_type: "",
            output_type: "",
          },
          {
            name: "lstm_bayesian",
            category: "benchmark",
            description: "",
            input_type: "",
            output_type: "",
          },
          {
            name: "lstm_siamese_bayesian",
            category: "benchmark",
            description: "",
            input_type: "",
            output_type: "",
          },
          {
            name: "standalone_lstm",
            category: "benchmark",
            description: "",
            input_type: "",
            output_type: "",
          },
          {
            name: "ensemble_methods",
            category: "benchmark",
            description: "",
            input_type: "",
            output_type: "",
          },
          {
            name: "decision_tree",
            category: "benchmark",
            description: "",
            input_type: "",
            output_type: "",
          },
          {
            name: "random_forest",
            category: "benchmark",
            description: "",
            input_type: "",
            output_type: "",
          },
          {
            name: "autoencoder",
            category: "benchmark",
            description: "",
            input_type: "",
            output_type: "",
          },
        ];
        setModels(placeholders);
        setSelected(placeholders.map((p) => p.name));
      });
  }, []);

  const handlePredict = async () => {
    if (!smilesA || !smilesB || selected.length === 0) return;
    setLoading(true);
    setError(null);
    try {
      const res = await predictMulti(smilesA, smilesB, selected);
      setResults(res);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setBatchFile(file);
    try {
      const text = await file.text();
      const lines = text.split('\n').map(l => l.trim()).filter(Boolean);
      if (lines.length < 2) {
        setError("CSV is empty or lacks rows");
        return;
      }
      const headers = lines[0].split(',').map(h => h.trim().toLowerCase());
      const idxA = headers.findIndex(h => h.includes('smiles_a') || h.includes('monomer_a'));
      const idxB = headers.findIndex(h => h.includes('smiles_b') || h.includes('monomer_b'));
      if (idxA === -1 || idxB === -1) {
        setError("CSV must contain columns for Monomer A and B SMILES (e.g. SMILES_A, SMILES_B)");
        return;
      }
      const parsed = [];
      for (let i = 1; i < lines.length; i++) {
         const cols = lines[i].split(',').map(c => c.trim().replace(/^"|"$/g, ''));
         if (cols.length > Math.max(idxA, idxB)) {
             parsed.push({ a: cols[idxA], b: cols[idxB] });
         }
      }
      setBatchRows(parsed);
      setError(null);
      setBatchResults([]);
    } catch (err: any) {
      setError("Failed to parse CSV: " + err.message);
    }
  };

  const handleBatchPredict = async () => {
    if (batchRows.length === 0 || selected.length === 0) return;
    setLoading(true);
    setError(null);
    setBatchResults([]);
    try {
      const allRes = [];
      // Prevent browser lockup while predicting batch sequentially
      for (const row of batchRows) {
        const res = await predictMulti(row.a, row.b, selected);
        allRes.push({ a: row.a, b: row.b, res });
      }
      setBatchResults(allRes);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Predict</h1>
        <p className="text-sm text-[var(--text-muted)]">
          Predict copolymerization reactivity ratios using our advanced models
        </p>
      </div>

      <div className="flex gap-4 border-b border-[var(--border)] pb-0 pt-2">
        <button
          onClick={() => setMode("single")}
          className={cn("pb-2 text-sm font-medium", mode === "single" ? "border-b-2 border-primary-500 text-white" : "text-[var(--text-muted)] hover:text-white")}
        >
          Single Pair
        </button>
        <button
          onClick={() => setMode("batch")}
          className={cn("pb-2 text-sm font-medium", mode === "batch" ? "border-b-2 border-primary-500 text-white" : "text-[var(--text-muted)] hover:text-white")}
        >
          Batch Upload (CSV)
        </button>
      </div>

      {/* Input section */}
      <div className="glass-card space-y-4">
        {mode === "single" ? (
          <div className="grid gap-4 md:grid-cols-2">
            <MoleculeInput
              label="Monomer A (SMILES)"
              value={smilesA}
              onChange={setSmilesA}
              placeholder="e.g. C=Cc1ccccc1 (Styrene)"
              valid={validA}
            />
            <MoleculeInput
              label="Monomer B (SMILES)"
              value={smilesB}
              onChange={setSmilesB}
              placeholder="e.g. C=C(C)C(=O)OC (MMA)"
              valid={validB}
            />
          </div>
        ) : (
          <div className="p-6 border border-dashed border-[var(--border)] rounded-lg text-center bg-white/[0.01]">
            <input type="file" accept=".csv" onChange={handleFileUpload} className="hidden" id="csv-upload" />
            <label htmlFor="csv-upload" className="cursor-pointer flex flex-col items-center">
              <Upload className="h-8 w-8 text-[var(--text-muted)] mb-3" />
              <span className="text-sm font-medium text-white">Click to upload CSV dataset</span>
              <span className="text-xs text-[var(--text-muted)] mt-1">Must contain columns like 'smiles_a' and 'smiles_b'</span>
            </label>
            {batchFile && (
              <div className="mt-4 inline-flex items-center gap-2 rounded-full bg-primary-500/10 px-3 py-1 text-xs text-primary-400">
                {batchFile.name} ({batchRows.length} pairs ready)
              </div>
            )}
          </div>
        )}

        <ModelSelector
          models={models}
          selected={selected}
          onChange={setSelected}
        />

        {mode === "single" ? (
          <button
            onClick={handlePredict}
            disabled={!smilesA || !smilesB || validA === false || validB === false || selected.length === 0 || loading}
            className="flex items-center gap-2 rounded-lg bg-primary-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Play className="h-4 w-4" />
            Run Prediction
            {selected.length > 1 ? `s (${selected.length} models)` : ""}
          </button>
        ) : (
          <button
            onClick={handleBatchPredict}
            disabled={batchRows.length === 0 || selected.length === 0 || loading}
            className="flex items-center gap-2 rounded-lg bg-primary-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Play className="h-4 w-4" />
            Run Batch Prediction ({batchRows.length} pairs × {selected.length} models)
          </button>
        )}

        {error && <p className="text-sm text-red-400">{error}</p>}
      </div>

      {loading && mode === "batch" && (
         <div className="glass-card flex items-center justify-center py-8">
            <p className="text-sm font-medium text-primary-400 animate-pulse">Running {batchRows.length * selected.length} predictions...</p>
         </div>
      )}

      {/* Results */}
      {mode === "single" ? (
        <>
          <ResultsPanel results={results} loading={loading} />
          {results.length > 0 && <PredictionBarChart results={results} />}
        </>
      ) : (
        batchResults.length > 0 && (
          <div className="glass-card overflow-x-auto">
            <h3 className="text-sm font-medium text-white mb-4">Batch Results</h3>
            <table className="w-full text-left text-sm">
              <thead className="border-b border-[var(--border)] text-[var(--text-muted)]">
                <tr>
                  <th className="pb-2 font-medium">SMILES A</th>
                  <th className="pb-2 font-medium">SMILES B</th>
                  <th className="pb-2 font-medium">Model</th>
                  <th className="pb-2 font-medium text-right">r₁</th>
                  <th className="pb-2 font-medium text-right">r₂</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {batchResults.flatMap((row, i) =>
                  row.res.map((r, j) => (
                    <tr key={`${i}-${j}`} className="group hover:bg-white/[0.02]">
                      <td className="py-2 text-[var(--text-muted)] truncate max-w-[150px]" title={row.a}>{row.a}</td>
                      <td className="py-2 text-[var(--text-muted)] truncate max-w-[150px]" title={row.b}>{row.b}</td>
                      <td className="py-2 text-white">{r.model.replace(/_/g, " ")}</td>
                      <td className="py-2 text-right font-medium text-primary-400">
                        {r.error ? <span className="text-red-400 text-xs">Error</span> : r.r1?.toFixed(4) ?? "—"}
                      </td>
                      <td className="py-2 text-right font-medium text-accent-400">
                        {r.error ? "-" : r.r2?.toFixed(4) ?? "—"}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )
      )}
    </div>
  );
}

