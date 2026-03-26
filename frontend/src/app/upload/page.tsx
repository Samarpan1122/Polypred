"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import {
  Upload,
  FileSpreadsheet,
  Trash2,
  Eye,
  BarChart3,
  ChevronDown,
  ChevronUp,
  AlertCircle,
  Globe2,
} from "lucide-react";
import {
  uploadDataset,
  listDatasets,
  getDatasetPreview,
  getDatasetStats,
  deleteDataset,
} from "@/lib/api";
import type { DatasetInfo, DatasetPreview, DatasetStats } from "@/lib/types";
import { useAuth } from "@/lib/contexts/AuthContext";
import { useRouter } from "next/navigation";
import PublicShareRequestModal from "@/components/PublicShareRequestModal";

export default function UploadPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const ownerId = user?.id || user?.email || "anonymous";

  useEffect(() => {
    if (!authLoading && !user) {
      router.push("/login");
    }
  }, [user, authLoading, router]);

  const [datasets, setDatasets] = useState<DatasetInfo[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [selectedDs, setSelectedDs] = useState<string | null>(null);
  const [preview, setPreview] = useState<DatasetPreview | null>(null);
  const [stats, setStats] = useState<DatasetStats | null>(null);
  const [showStats, setShowStats] = useState(false);
  const [shareTarget, setShareTarget] = useState<DatasetInfo | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    try {
      const ds = await listDatasets(ownerId);
      setDatasets(ds);
    } catch {
      /* empty */
    }
  }, [ownerId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleUpload = async (file: File) => {
    setUploading(true);
    setError(null);
    try {
      await uploadDataset(file, ownerId);
      await refresh();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const f = e.dataTransfer.files[0];
      if (f) handleUpload(f);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  const selectDs = async (id: string) => {
    setSelectedDs(id);
    setPreview(null);
    setStats(null);
    setShowStats(false);
    try {
      const [p, s] = await Promise.all([
        getDatasetPreview(id, ownerId, 50),
        getDatasetStats(id, ownerId),
      ]);
      setPreview(p);
      setStats(s);
    } catch {
      /* empty */
    }
  };

  const removeDaset = async (id: string) => {
    try {
      await deleteDataset(id, ownerId);
      if (selectedDs === id) {
        setSelectedDs(null);
        setPreview(null);
        setStats(null);
      }
      await refresh();
    } catch {
      /* empty */
    }
  };

  if (authLoading || !user) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <div className="text-white">Loading...</div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Upload Dataset</h1>
        <p className="text-sm text-[var(--text-muted)]">
          Upload a CSV with monomer SMILES pairs and reactivity ratios
        </p>
      </div>

      {/* Drop zone */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onClick={() => fileRef.current?.click()}
        className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed p-12 transition-colors ${
          dragOver
            ? "border-primary-400 bg-primary-600/10"
            : "border-[var(--border)] hover:border-primary-400/50 hover:bg-[var(--bg-hover)]"
        }`}
      >
        <Upload
          className={`mb-3 h-10 w-10 ${
            dragOver ? "text-primary-400" : "text-[var(--text-muted)]"
          }`}
        />
        <p className="text-sm font-medium text-white">
          {uploading ? "Uploading..." : "Drop CSV here or click to browse"}
        </p>
        <p className="mt-1 text-xs text-[var(--text-muted)]">
          .csv files with SMILES columns (auto-detected)
        </p>
        <input
          ref={fileRef}
          type="file"
          accept=".csv"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) handleUpload(f);
          }}
        />
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg bg-red-500/10 px-4 py-2 text-sm text-red-400">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      )}

      {/* Dataset list */}
      {datasets.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-lg font-semibold text-white">Your Datasets</h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {datasets.map((ds) => (
              <div
                key={ds.id}
                className={`glass-card cursor-pointer rounded-xl p-4 transition-all ${
                  selectedDs === ds.id
                    ? "ring-2 ring-primary-400"
                    : "hover:ring-1 hover:ring-primary-400/30"
                }`}
                onClick={() => selectDs(ds.id)}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    <FileSpreadsheet className="h-5 w-5 text-primary-400" />
                    <span className="font-medium text-white">{ds.name}</span>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      removeDaset(ds.id);
                    }}
                    className="rounded p-1 text-[var(--text-muted)] hover:bg-red-500/20 hover:text-red-400"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
                <div className="mt-2 flex flex-wrap gap-3 text-xs text-[var(--text-muted)]">
                  <span>{ds.rows} rows</span>
                  <span>{ds.cols} cols</span>
                </div>
                {(ds.smiles_columns?.length ?? 0) > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {ds.smiles_columns?.map((c) => (
                      <span
                        key={c}
                        className="rounded-full bg-blue-500/10 px-2 py-0.5 text-[10px] text-blue-400"
                      >
                        {c}
                      </span>
                    ))}
                    {ds.target_columns?.map((c) => (
                      <span
                        key={c}
                        className="rounded-full bg-green-500/10 px-2 py-0.5 text-[10px] text-green-400"
                      >
                        {c}
                      </span>
                    ))}
                  </div>
                )}
                <div className="mt-3 border-t border-[var(--border)] pt-2">
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      setShareTarget(ds);
                    }}
                    className="inline-flex items-center gap-1 rounded-md border border-primary-500/40 bg-primary-500/10 px-2 py-1 text-[11px] text-primary-300 hover:bg-primary-500/20"
                  >
                    <Globe2 className="h-3.5 w-3.5" />
                    Make Public
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Data preview */}
      {preview && selectedDs && (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <Eye className="h-5 w-5 text-primary-400" />
            <h2 className="text-lg font-semibold text-white">Data Preview</h2>
            <span className="rounded bg-[var(--bg-hover)] px-2 py-0.5 text-xs text-[var(--text-muted)]">
              {preview.shape[0]} × {preview.shape[1]}
            </span>
            <button
              onClick={() => setShowStats(!showStats)}
              className="ml-auto flex items-center gap-1 rounded-lg bg-[var(--bg-hover)] px-3 py-1.5 text-xs text-[var(--text-muted)] hover:text-white"
            >
              <BarChart3 className="h-3 w-3" />
              Stats
              {showStats ? (
                <ChevronUp className="h-3 w-3" />
              ) : (
                <ChevronDown className="h-3 w-3" />
              )}
            </button>
          </div>

          {/* Stats panel */}
          {showStats && stats && (
            <div className="glass-card overflow-x-auto rounded-xl p-4">
              <table className="min-w-full text-xs">
                <thead>
                  <tr className="border-b border-[var(--border)]">
                    <th className="px-3 py-2 text-left text-[var(--text-muted)]">
                      Column
                    </th>
                    <th className="px-3 py-2 text-right text-[var(--text-muted)]">
                      Mean
                    </th>
                    <th className="px-3 py-2 text-right text-[var(--text-muted)]">
                      Std
                    </th>
                    <th className="px-3 py-2 text-right text-[var(--text-muted)]">
                      Min
                    </th>
                    <th className="px-3 py-2 text-right text-[var(--text-muted)]">
                      Max
                    </th>
                    <th className="px-3 py-2 text-right text-[var(--text-muted)]">
                      Median
                    </th>
                    <th className="px-3 py-2 text-right text-[var(--text-muted)]">
                      Missing
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(stats.column_stats || {}).map(([col, s]) => (
                    <tr
                      key={col}
                      className="border-b border-[var(--border)]/30"
                    >
                      <td className="px-3 py-1.5 font-medium text-white">
                        {col}
                      </td>
                      <td className="px-3 py-1.5 text-right text-[var(--text-secondary)]">
                        {typeof s.mean === "number" ? s.mean.toFixed(4) : "-"}
                      </td>
                      <td className="px-3 py-1.5 text-right text-[var(--text-secondary)]">
                        {typeof s.std === "number" ? s.std.toFixed(4) : "-"}
                      </td>
                      <td className="px-3 py-1.5 text-right text-[var(--text-secondary)]">
                        {typeof s.min === "number" ? s.min.toFixed(4) : "-"}
                      </td>
                      <td className="px-3 py-1.5 text-right text-[var(--text-secondary)]">
                        {typeof s.max === "number" ? s.max.toFixed(4) : "-"}
                      </td>
                      <td className="px-3 py-1.5 text-right text-[var(--text-secondary)]">
                        {typeof s.median === "number"
                          ? s.median.toFixed(4)
                          : "-"}
                      </td>
                      <td className="px-3 py-1.5 text-right text-[var(--text-secondary)]">
                        {s.missing}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Data table */}
          <div className="glass-card overflow-x-auto rounded-xl">
            <table className="min-w-full text-xs">
              <thead>
                <tr className="border-b border-[var(--border)]">
                  <th className="sticky left-0 bg-[var(--bg-card)] px-3 py-2 text-left text-[var(--text-muted)]">
                    #
                  </th>
                  {preview.columns.map((col) => (
                    <th
                      key={col}
                      className="px-3 py-2 text-left text-[var(--text-muted)]"
                    >
                      <div className="flex flex-col">
                        <span>{col}</span>
                        <span className="text-[10px] font-normal opacity-60">
                          {preview.dtypes[col]}
                        </span>
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {preview.rows.map((row, ri) => (
                  <tr
                    key={ri}
                    className="border-b border-[var(--border)]/20 hover:bg-[var(--bg-hover)]"
                  >
                    <td className="sticky left-0 bg-[var(--bg-card)] px-3 py-1.5 text-[var(--text-muted)]">
                      {ri + 1}
                    </td>
                    {preview.columns.map((col) => (
                      <td
                        key={col}
                        className="max-w-[200px] truncate px-3 py-1.5 text-[var(--text-secondary)]"
                      >
                        {String(row[col] ?? "")}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {shareTarget && (
        <PublicShareRequestModal
          isOpen={!!shareTarget}
          assetType="dataset"
          assetId={shareTarget.id}
          assetName={shareTarget.name}
          onClose={() => setShareTarget(null)}
        />
      )}
    </div>
  );
}
