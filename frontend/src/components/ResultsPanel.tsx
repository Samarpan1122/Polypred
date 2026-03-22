"use client";

import type { PredictResponse } from "@/lib/types";
import { cn } from "@/lib/utils";
import { AlertCircle, Clock, FlaskConical } from "lucide-react";

interface Props {
  results: PredictResponse[];
  loading?: boolean;
}

export default function ResultsPanel({ results, loading }: Props) {
  if (loading) {
    return (
      <div className="glass-card loading-pulse flex items-center justify-center py-16">
        <div className="text-center">
          <FlaskConical className="mx-auto h-8 w-8 animate-spin text-primary-400" />
          <p className="mt-3 text-sm text-[var(--text-muted)]">
            Running predictions…
          </p>
        </div>
      </div>
    );
  }

  if (results.length === 0) {
    return (
      <div className="glass-card flex items-center justify-center py-16 text-center">
        <div>
          <FlaskConical className="mx-auto h-8 w-8 text-[var(--text-muted)]" />
          <p className="mt-3 text-sm text-[var(--text-muted)]">
            Enter two monomer SMILES and select model(s) to see predictions
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {results.map((r) => (
        <div
          key={r.model}
          className={cn(
            "glass-card flex items-center justify-between",
            r.error && "border-red-500/30",
          )}
        >
          <div className="flex items-center gap-4">
            <div>
              <p className="text-sm font-semibold text-white">
                {r.model.replace(/_/g, " ")}
              </p>
              {r.error ? (
                <p className="flex items-center gap-1 text-xs text-red-400">
                  <AlertCircle className="h-3 w-3" />
                  {r.error}
                </p>
              ) : (
                <div className="flex items-center gap-1 text-xs text-[var(--text-muted)]">
                  <Clock className="h-3 w-3" />
                  {r.latency_ms?.toFixed(1)} ms
                </div>
              )}
            </div>
          </div>

          {!r.error && (
            <div className="flex gap-6">
              <div className="text-right">
                <p className="text-xs text-[var(--text-muted)]">r₁</p>
                <p className="text-lg font-bold text-primary-400">
                  {r.r1?.toFixed(4) ?? "—"}
                </p>
              </div>
              <div className="text-right">
                <p className="text-xs text-[var(--text-muted)]">r₂</p>
                <p className="text-lg font-bold text-accent-400">
                  {r.r2?.toFixed(4) ?? "—"}
                </p>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
