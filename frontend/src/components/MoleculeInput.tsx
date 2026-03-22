"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { AlertCircle, CheckCircle2 } from "lucide-react";

interface Props {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  valid?: boolean | null;
}

const EXAMPLE_SMILES = [
  { label: "Styrene", smiles: "C=Cc1ccccc1" },
  { label: "Methyl methacrylate", smiles: "C=C(C)C(=O)OC" },
  { label: "Vinyl acetate", smiles: "C=COC(C)=O" },
  { label: "Acrylonitrile", smiles: "C=CC#N" },
  { label: "Butadiene", smiles: "C=CC=C" },
  { label: "Acrylic acid", smiles: "C=CC(=O)O" },
];

export default function MoleculeInput({
  label,
  value,
  onChange,
  placeholder = "Enter SMILES...",
  valid,
}: Props) {
  const [showExamples, setShowExamples] = useState(false);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-[var(--text)]">
          {label}
        </label>
        <button
          type="button"
          onClick={() => setShowExamples(!showExamples)}
          className="text-xs text-primary-400 hover:text-primary-300"
        >
          {showExamples ? "Hide" : "Examples"}
        </button>
      </div>

      <div className="relative">
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className={cn(
            "smiles-input w-full pr-10",
            valid === true &&
              "border-accent-500 focus:border-accent-500 focus:ring-accent-500",
            valid === false &&
              "border-red-500 focus:border-red-500 focus:ring-red-500",
          )}
        />
        {valid !== null && valid !== undefined && (
          <div className="absolute right-3 top-1/2 -translate-y-1/2">
            {valid ? (
              <CheckCircle2 className="h-4 w-4 text-accent-500" />
            ) : (
              <AlertCircle className="h-4 w-4 text-red-500" />
            )}
          </div>
        )}
      </div>

      {showExamples && (
        <div className="flex flex-wrap gap-2">
          {EXAMPLE_SMILES.map((ex) => (
            <button
              key={ex.smiles}
              type="button"
              onClick={() => {
                onChange(ex.smiles);
                setShowExamples(false);
              }}
              className="rounded-md border border-[var(--border)] bg-[var(--bg)] px-2.5 py-1 text-xs text-[var(--text-muted)] hover:border-primary-500 hover:text-primary-400"
            >
              {ex.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
