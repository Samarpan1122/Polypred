"use client";

import type { PredictResponse } from "@/lib/types";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
  ScatterChart,
  Scatter,
  ZAxis,
} from "recharts";

// ─── Bar chart: r₁ & r₂ per model ─────────────────────────
interface BarProps {
  results: PredictResponse[];
}

export function PredictionBarChart({ results }: BarProps) {
  const data = results
    .filter((r) => !r.error)
    .map((r) => ({
      model: r.model.replace(/_/g, " "),
      r1: r.r1 ?? 0,
      r2: r.r2 ?? 0,
    }));

  if (data.length === 0) return null;

  return (
    <div className="glass-card">
      <h3 className="mb-4 text-sm font-medium text-[var(--text)]">
        Predicted Reactivity Ratios by Model
      </h3>
      <ResponsiveContainer
        width="100%"
        height={Math.max(300, data.length * 40)}
      >
        <BarChart
          data={data}
          layout="vertical"
          margin={{ left: 120, right: 20, top: 5, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#2a2a3a" />
          <XAxis type="number" stroke="#8888a0" tick={{ fontSize: 11 }} />
          <YAxis
            dataKey="model"
            type="category"
            stroke="#8888a0"
            tick={{ fontSize: 11 }}
            width={110}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#111118",
              border: "1px solid #2a2a3a",
              borderRadius: 8,
              fontSize: 12,
            }}
          />
          <Legend />
          <Bar dataKey="r1" name="r₁" fill="#3b82f6" radius={[0, 4, 4, 0]} />
          <Bar dataKey="r2" name="r₂" fill="#22c55e" radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ─── Scatter: r₁ vs r₂ ─────────────────────────────────────
export function R1R2ScatterChart({ results }: BarProps) {
  const data = results
    .filter((r) => !r.error && r.r1 != null && r.r2 != null)
    .map((r) => ({
      model: r.model.replace(/_/g, " "),
      r1: r.r1!,
      r2: r.r2!,
      latency: r.latency_ms ?? 1,
    }));

  if (data.length < 2) return null;

  return (
    <div className="glass-card">
      <h3 className="mb-4 text-sm font-medium text-[var(--text)]">
        r₁ vs r₂ Scatter (size = latency)
      </h3>
      <ResponsiveContainer width="100%" height={350}>
        <ScatterChart margin={{ left: 10, right: 20, top: 10, bottom: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#2a2a3a" />
          <XAxis
            dataKey="r1"
            name="r₁"
            type="number"
            stroke="#8888a0"
            tick={{ fontSize: 11 }}
            label={{
              value: "r₁",
              position: "insideBottom",
              offset: -5,
              fill: "#8888a0",
            }}
          />
          <YAxis
            dataKey="r2"
            name="r₂"
            type="number"
            stroke="#8888a0"
            tick={{ fontSize: 11 }}
            label={{
              value: "r₂",
              angle: -90,
              position: "insideLeft",
              fill: "#8888a0",
            }}
          />
          <ZAxis dataKey="latency" range={[50, 400]} name="latency (ms)" />
          <Tooltip
            cursor={{ strokeDasharray: "3 3" }}
            contentStyle={{
              backgroundColor: "#111118",
              border: "1px solid #2a2a3a",
              borderRadius: 8,
              fontSize: 12,
            }}
            formatter={(value: number, name: string) => [
              value.toFixed(4),
              name,
            ]}
          />
          <Scatter data={data} fill="#3b82f6" name="Models" shape="circle" />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}

// ─── Latency bar chart ──────────────────────────────────────
export function LatencyChart({ results }: BarProps) {
  const data = results
    .filter((r) => !r.error)
    .map((r) => ({
      model: r.model.replace(/_/g, " "),
      latency: r.latency_ms ?? 0,
    }))
    .sort((a, b) => a.latency - b.latency);

  if (data.length === 0) return null;

  return (
    <div className="glass-card">
      <h3 className="mb-4 text-sm font-medium text-[var(--text)]">
        Inference Latency (ms)
      </h3>
      <ResponsiveContainer
        width="100%"
        height={Math.max(250, data.length * 30)}
      >
        <BarChart
          data={data}
          layout="vertical"
          margin={{ left: 120, right: 20, top: 5, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#2a2a3a" />
          <XAxis type="number" stroke="#8888a0" tick={{ fontSize: 11 }} />
          <YAxis
            dataKey="model"
            type="category"
            stroke="#8888a0"
            tick={{ fontSize: 11 }}
            width={110}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#111118",
              border: "1px solid #2a2a3a",
              borderRadius: 8,
              fontSize: 12,
            }}
          />
          <Bar
            dataKey="latency"
            name="Latency (ms)"
            fill="#a855f7"
            radius={[0, 4, 4, 0]}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
