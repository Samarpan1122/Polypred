"use client";

import { getPublicCatalog } from "@/lib/api";
import type { PublicCatalogItem } from "@/lib/types";
import {
  BarChart3,
  BookOpen,
  Database,
  Globe2,
  Microscope,
  UserRound,
} from "lucide-react";
import { useEffect, useState, type ComponentType } from "react";

export default function PublicDatasetsModelsPage() {
  const [tab, setTab] = useState<"datasets" | "models">("datasets");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [datasets, setDatasets] = useState<PublicCatalogItem[]>([]);
  const [models, setModels] = useState<PublicCatalogItem[]>([]);
  const [summary, setSummary] = useState({
    datasets: 0,
    models: 0,
    total: 0,
  });

  useEffect(() => {
    getPublicCatalog()
      .then((res) => {
        setDatasets(res.datasets);
        setModels(res.models);
        setSummary(res.summary);
      })
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Could not load public assets."),
      )
      .finally(() => setLoading(false));
  }, []);

  const activeItems = tab === "datasets" ? datasets : models;

  return (
    <div className="space-y-8 py-6">
      <section className="relative overflow-hidden rounded-[28px] border border-[var(--border)] bg-[radial-gradient(circle_at_top_left,rgba(59,130,246,0.24),transparent_40%),linear-gradient(135deg,rgba(15,23,42,0.96),rgba(8,15,32,0.96))] p-8">
        <div className="absolute right-0 top-0 h-40 w-40 rounded-full bg-cyan-400/10 blur-3xl" />
        <div className="relative max-w-3xl">
          <div className="inline-flex items-center gap-2 rounded-full border border-primary-400/30 bg-primary-500/10 px-3 py-1 text-xs font-bold uppercase tracking-[0.2em] text-primary-200">
            <Globe2 className="h-3.5 w-3.5" />
            Public Research Hub
          </div>
          <h1 className="mt-4 text-4xl font-black tracking-tight text-white">
            Public Datasets and Models
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-300">
            This page lists datasets and models that were submitted by users,
            reviewed by an admin, and approved for public visibility.
          </p>
        </div>
      </section>

      <div className="grid gap-4 md:grid-cols-3">
        <StatCard label="Public Datasets" value={summary.datasets} icon={Database} />
        <StatCard label="Public Models" value={summary.models} icon={BarChart3} />
        <StatCard label="Total Public Assets" value={summary.total} icon={Microscope} />
      </div>

      <div className="glass-card">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-white">Approved Assets</h2>
            <p className="text-sm text-[var(--text-muted)]">
              Browse publicly approved contributions across the platform.
            </p>
          </div>
          <div className="flex gap-2">
            {(["datasets", "models"] as const).map((value) => (
              <button
                key={value}
                onClick={() => setTab(value)}
                className={`rounded-lg border px-4 py-2 text-sm font-semibold capitalize ${
                  tab === value
                    ? "border-primary-400 bg-primary-500/10 text-primary-200"
                    : "border-[var(--border)] text-[var(--text-muted)] hover:text-white"
                }`}
              >
                {value}
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <div className="mt-6 rounded-xl border border-[var(--border)] px-4 py-10 text-center text-sm text-[var(--text-muted)]">
            Loading public assets...
          </div>
        ) : error ? (
          <div className="mt-6 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-4 text-sm text-red-200">
            {error}
          </div>
        ) : activeItems.length === 0 ? (
          <div className="mt-6 rounded-xl border border-[var(--border)] px-4 py-10 text-center text-sm text-[var(--text-muted)]">
            No approved {tab} yet.
          </div>
        ) : (
          <div className="mt-6 grid gap-4 lg:grid-cols-2">
            {activeItems.map((item) => (
              <article
                key={item.request_id}
                className="rounded-2xl border border-[var(--border)] bg-white/[0.03] p-5"
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <span className="inline-flex rounded-full border border-primary-500/30 bg-primary-500/10 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-primary-200">
                      {item.asset_type}
                    </span>
                    <h3 className="mt-3 text-xl font-semibold text-white">
                      {item.asset_name}
                    </h3>
                    <p className="mt-1 text-sm text-[var(--text-muted)]">
                      {item.research_area}
                    </p>
                  </div>
                  <p className="text-right text-xs text-[var(--text-muted)]">
                    Approved {formatDate(item.approved_at)}
                  </p>
                </div>

                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <MetaPill icon={UserRound} text={item.requester_name} />
                  <MetaPill icon={BookOpen} text={item.affiliation} />
                </div>

                <div className="mt-4 space-y-4">
                  <Section label="Research Title" value={item.research_title} />
                  <Section label="Summary" value={item.research_summary} />
                  <Section label="Intended Use" value={item.intended_use} />
                  {item.citation_text ? (
                    <Section label="Citation / DOI" value={item.citation_text} />
                  ) : null}
                  {item.profile_url ? (
                    <a
                      href={item.profile_url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-2 text-sm text-primary-300 hover:text-primary-200"
                    >
                      <Globe2 className="h-4 w-4" />
                      Research profile
                    </a>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function formatDate(value?: string | null) {
  if (!value) return "-";
  return new Date(value).toLocaleDateString();
}

function StatCard({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: number;
  icon: ComponentType<{ className?: string }>;
}) {
  return (
    <div className="glass-card flex items-start gap-4">
      <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary-500/10 text-primary-300">
        <Icon className="h-5 w-5" />
      </div>
      <div>
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-[var(--text-muted)]">
          {label}
        </p>
        <p className="mt-2 text-3xl font-black text-white">{value}</p>
      </div>
    </div>
  );
}

function MetaPill({
  icon: Icon,
  text,
}: {
  icon: ComponentType<{ className?: string }>;
  text: string;
}) {
  return (
    <div className="inline-flex items-center gap-2 rounded-xl border border-[var(--border)] bg-black/10 px-3 py-2 text-sm text-white">
      <Icon className="h-4 w-4 text-primary-300" />
      {text}
    </div>
  );
}

function Section({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-black/10 p-4">
      <p className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
        {label}
      </p>
      <p className="mt-2 text-sm leading-6 text-white">{value}</p>
    </div>
  );
}
