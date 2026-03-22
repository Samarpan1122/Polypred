"use client";

import { cn } from "@/lib/utils";
import type { ModelCategory } from "@/lib/types";
import { MODEL_CATEGORY_LABELS } from "@/lib/types";

interface Props {
  models: { name: string; category: string }[];
  selected: string[];
  onChange: (selected: string[]) => void;
  multi?: boolean;
}

const CATEGORY_ORDER: ModelCategory[] = [
  "deep_learning",
  "traditional_ml",
  "traditional",
  "encoder",
  "siamese",
  "generative",
  "benchmark",
  "unknown",
];

const CATEGORY_BADGE_COLORS: Record<string, string> = {
  deep_learning: "bg-blue-500/10 text-blue-400 border-blue-500/30",
  traditional_ml: "bg-green-500/10 text-green-400 border-green-500/30",
  traditional: "bg-green-500/10 text-green-400 border-green-500/30",
  encoder: "bg-purple-500/10 text-purple-400 border-purple-500/30",
  siamese: "bg-amber-500/10 text-amber-400 border-amber-500/30",
  generative: "bg-pink-500/10 text-pink-400 border-pink-500/30",
  benchmark: "bg-orange-500/10 text-orange-400 border-orange-500/30",
  unknown: "bg-teal-500/10 text-teal-400 border-teal-500/30",
};

export default function ModelSelector({
  models,
  selected,
  onChange,
  multi = true,
}: Props) {
  const grouped = CATEGORY_ORDER.map((cat) => ({
    category: cat,
    label: MODEL_CATEGORY_LABELS[cat],
    items: models.filter((m) => m.category === cat),
  })).filter((g) => g.items.length > 0);

  const toggle = (name: string) => {
    if (multi) {
      onChange(
        selected.includes(name)
          ? selected.filter((s) => s !== name)
          : [...selected, name],
      );
    } else {
      onChange([name]);
    }
  };

  const selectCategory = (cat: string) => {
    const names = models.filter((m) => m.category === cat).map((m) => m.name);
    const allSelected = names.every((n) => selected.includes(n));
    if (allSelected) {
      onChange(selected.filter((s) => !names.includes(s)));
    } else {
      onChange([...new Set([...selected, ...names])]);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-[var(--text)]">
          Select Models
        </h3>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() =>
              onChange(
                models
                  .filter((m) => m.category !== "encoder")
                  .map((m) => m.name),
              )
            }
            className="text-xs text-primary-400 hover:text-primary-300"
          >
            Select All
          </button>
          <button
            type="button"
            onClick={() => onChange([])}
            className="text-xs text-[var(--text-muted)] hover:text-white"
          >
            Clear
          </button>
        </div>
      </div>

      {grouped.map((group) => (
        <div key={group.category} className="space-y-2">
          <button
            type="button"
            onClick={() => selectCategory(group.category)}
            className={cn(
              "inline-block rounded-md border px-2 py-0.5 text-xs font-medium",
              CATEGORY_BADGE_COLORS[group.category] ||
                "bg-gray-500/10 text-gray-400 border-gray-500/30",
            )}
          >
            {group.label}
          </button>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
            {group.items.map((m) => {
              const active = selected.includes(m.name);
              return (
                <button
                  key={m.name}
                  type="button"
                  onClick={() => toggle(m.name)}
                  className={cn(
                    "rounded-lg border px-3 py-2 text-left text-xs transition-colors",
                    active
                      ? "border-primary-500 bg-primary-600/10 text-primary-300"
                      : "border-[var(--border)] bg-[var(--bg)] text-[var(--text-muted)] hover:border-[var(--text-muted)]",
                  )}
                >
                  {m.name.replace(/_/g, " ")}
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
