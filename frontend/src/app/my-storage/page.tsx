"use client";

import { useAuth } from "@/lib/contexts/AuthContext";
import { getUserDownloadUrl, listUserFiles } from "@/lib/api";
import type { StorageFileItem } from "@/lib/types";
import {
  Download,
  FolderLock,
  HardDrive,
  RefreshCw,
  ShieldCheck,
  Database,
  AlertCircle,
  FolderOpen,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

export default function MyStoragePage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const ownerId = user?.id || user?.email || "anonymous";
  const [section, setSection] = useState<
    "all" | "datasets" | "models" | "results" | "requests"
  >("datasets");
  const [files, setFiles] = useState<StorageFileItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [encryptionMode, setEncryptionMode] = useState("unknown");

  const loadFiles = async () => {
    if (!ownerId) return;
    setBusy(true);
    setError(null);
    try {
      const resp = await listUserFiles(ownerId, section, 120);
      setFiles(resp.files);
      setEncryptionMode(resp.encryption.mode || "unknown");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not load your files.",
      );
      setFiles([]);
    } finally {
      setBusy(false);
    }
  };

  const onDownload = async (key: string) => {
    if (!ownerId) return;
    try {
      const resp = await getUserDownloadUrl(ownerId, key, 300);
      window.open(resp.url, "_blank", "noopener,noreferrer");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not create download URL.",
      );
    }
  };

  const formatBytes = (bytes: number) => {
    if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
    const units = ["B", "KB", "MB", "GB", "TB"];
    const idx = Math.min(
      Math.floor(Math.log(bytes) / Math.log(1024)),
      units.length - 1,
    );
    return `${(bytes / 1024 ** idx).toFixed(idx === 0 ? 0 : 2)} ${units[idx]}`;
  };

  useEffect(() => {
    if (!loading && !user) {
      router.push("/login");
    }
  }, [user, loading, router]);

  useEffect(() => {
    if (!loading && user) {
      loadFiles();
    }
  }, [user, loading, section]);

  if (loading || !user) return null;

  return (
    <div className="space-y-8 py-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">My Files</h1>
          <p className="text-[var(--text-muted)] mt-1">
            Browse only your datasets, models, and results in AES-256 encrypted
            storage.
          </p>
        </div>
        <button
          onClick={loadFiles}
          disabled={busy}
          className="inline-flex items-center gap-2 rounded-lg border border-[var(--border)] px-3 py-2 text-sm font-semibold text-white hover:bg-white/5 disabled:opacity-60"
        >
          <RefreshCw className={`h-4 w-4 ${busy ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        <div className="glass-card flex items-start gap-4">
          <div className="h-10 w-10 rounded-lg bg-primary-600/10 flex items-center justify-center text-primary-400">
            <HardDrive className="h-5 w-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">
              Visible Files
            </h3>
            <p className="text-2xl font-black text-white mt-1">
              {files.length}
            </p>
            <p className="text-xs text-[var(--text-muted)] mt-1">
              Section: {section}
            </p>
          </div>
        </div>

        <div className="glass-card flex items-start gap-4">
          <div className="h-10 w-10 rounded-lg bg-green-600/10 flex items-center justify-center text-green-400">
            <ShieldCheck className="h-5 w-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">
              Encryption Status
            </h3>
            <p className="text-lg font-bold text-white mt-1">
              {encryptionMode.toUpperCase()}
            </p>
            <p className="text-xs text-[var(--text-muted)] mt-1 truncate max-w-[280px]">
              SSE-S3 managed encryption active
            </p>
          </div>
        </div>

        <div className="glass-card flex items-start gap-4">
          <div className="h-10 w-10 rounded-lg bg-amber-600/10 flex items-center justify-center text-amber-400">
            <FolderLock className="h-5 w-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">
              Owner Scope
            </h3>
            <p className="text-sm font-semibold text-white mt-1 break-all">
              {ownerId}
            </p>
            <p className="text-xs text-[var(--text-muted)] mt-1">
              Only keys under your prefix are listed.
            </p>
          </div>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {(["all", "datasets", "models", "results", "requests"] as const).map(
          (s) => (
            <button
              key={s}
              onClick={() => setSection(s)}
              className={`rounded-lg border px-3 py-1.5 text-xs font-bold uppercase tracking-wider transition-colors ${
                section === s
                  ? "border-primary-400 bg-primary-500/10 text-primary-300"
                  : "border-[var(--border)] text-[var(--text-muted)] hover:text-white"
              }`}
            >
              {s}
            </button>
          ),
        )}
      </div>

      {error ? (
        <div className="glass-card border border-red-500/30 bg-red-500/10 text-red-300 flex items-start gap-3">
          <AlertCircle className="h-5 w-5 mt-0.5" />
          <p className="text-sm">{error}</p>
        </div>
      ) : null}

      <div className="glass-card p-0 overflow-hidden">
        <div className="border-b border-[var(--border)] px-6 py-4 bg-white/5 flex justify-between items-center">
          <h3 className="text-sm font-bold text-white uppercase tracking-widest flex items-center gap-2">
            <FolderOpen className="h-4 w-4 text-primary-400" />
            User File Browser
          </h3>
        </div>
        {busy ? (
          <div className="px-6 py-10 text-center text-sm text-[var(--text-muted)]">
            Loading files...
          </div>
        ) : files.length === 0 ? (
          <div className="px-6 py-10 text-center text-sm text-[var(--text-muted)]">
            No files found in this section.
          </div>
        ) : (
          <div className="divide-y divide-[var(--border)]">
            {files.map((item) => {
              const encrypted = item.encryption === "AES256";
              return (
                <div
                  key={item.key}
                  className="px-6 py-4 flex items-center justify-between hover:bg-white/5 transition-colors group gap-4"
                >
                  <div className="flex items-start gap-3 min-w-0">
                    <Database className="h-5 w-5 text-[var(--text-muted)] group-hover:text-primary-400 mt-0.5 shrink-0" />
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-white truncate">
                        {item.name}
                      </p>
                      <p className="text-[10px] text-[var(--text-muted)] uppercase font-bold mt-0.5 break-all">
                        {item.key}
                      </p>
                      <div className="mt-1 flex items-center gap-2 text-[10px]">
                        <span className="text-[var(--text-muted)]">
                          {formatBytes(item.size)}
                        </span>
                        <span className="text-[var(--text-muted)]">
                          {item.storage_class}
                        </span>
                        <span
                          className={`rounded px-1.5 py-0.5 font-bold ${encrypted ? "bg-green-500/10 text-green-300" : "bg-amber-500/10 text-amber-300"}`}
                        >
                          {item.encryption || "unknown"}
                        </span>
                      </div>
                    </div>
                  </div>
                  <button
                    onClick={() => onDownload(item.key)}
                    disabled={item.downloadable === false}
                    className="inline-flex items-center gap-2 rounded border border-[var(--border)] px-2.5 py-1.5 text-xs font-semibold text-white hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
                    title={
                      item.downloadable === false
                        ? "This file is still syncing to S3"
                        : "Download"
                    }
                  >
                    <Download className="h-3.5 w-3.5" />
                    Download
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
