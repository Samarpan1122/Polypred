"use client";

import {
  getAdminOverview,
  listAdminPublicShareRequests,
  reviewPublicShareRequest,
} from "@/lib/api";
import { useAuth } from "@/lib/contexts/AuthContext";
import type {
  AdminOverviewResponse,
  PublicShareRequestRecord,
} from "@/lib/types";
import {
  BarChart3,
  CheckCircle2,
  Clock3,
  Database,
  Globe2,
  Shield,
  Users,
  XCircle,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

const FILTERS = ["all", "pending_review", "approved", "rejected"] as const;

export default function AdminPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [overview, setOverview] = useState<AdminOverviewResponse | null>(null);
  const [requests, setRequests] = useState<PublicShareRequestRecord[]>([]);
  const [filter, setFilter] =
    useState<(typeof FILTERS)[number]>("pending_review");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notesById, setNotesById] = useState<Record<string, string>>({});

  const adminEmail = user?.email || "";

  const loadAdminData = async (selectedFilter = filter) => {
    if (!adminEmail) return;
    setBusy(true);
    setError(null);
    try {
      const [overviewRes, requestsRes] = await Promise.all([
        getAdminOverview(adminEmail),
        listAdminPublicShareRequests(adminEmail, selectedFilter),
      ]);
      setOverview(overviewRes);
      setRequests(requestsRes.requests);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not load admin data.",
      );
    } finally {
      setBusy(false);
    }
  };

  const onReview = async (
    requestId: string,
    decision: "approved" | "rejected",
  ) => {
    if (!adminEmail) return;
    setBusy(true);
    setError(null);
    try {
      await reviewPublicShareRequest(
        adminEmail,
        requestId,
        decision,
        notesById[requestId] || "",
      );
      await loadAdminData(filter);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Review action failed.");
      setBusy(false);
    }
  };

  useEffect(() => {
    if (!loading && !user) {
      router.push("/login");
    } else if (!loading && user && !user.isAdmin) {
      router.push("/");
    }
  }, [loading, router, user]);

  useEffect(() => {
    if (!loading && user?.isAdmin) {
      loadAdminData(filter);
    }
  }, [loading, user, filter]);

  if (loading || !user) return null;
  if (!user.isAdmin) return null;

  const stats = overview?.stats;
  const statCards = [
    { label: "Users", value: stats?.users ?? 0, icon: Users },
    { label: "Datasets", value: stats?.datasets ?? 0, icon: Database },
    { label: "Models", value: stats?.models ?? 0, icon: BarChart3 },
    { label: "Pending Review", value: stats?.pending_requests ?? 0, icon: Clock3 },
    { label: "Public Datasets", value: stats?.public_datasets ?? 0, icon: Globe2 },
    { label: "Public Models", value: stats?.public_models ?? 0, icon: CheckCircle2 },
  ];

  return (
    <div className="space-y-8 py-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-white">Admin Console</h1>
          <p className="mt-1 text-[var(--text-muted)]">
            Review public listing requests and monitor platform-level stats.
          </p>
        </div>
        <div className="rounded-xl border border-primary-500/30 bg-primary-500/10 px-4 py-2 text-sm text-primary-100">
          Signed in as admin: {adminEmail}
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {statCards.map((card) => (
          <div key={card.label} className="glass-card flex items-start gap-4">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary-500/10 text-primary-300">
              <card.icon className="h-5 w-5" />
            </div>
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.2em] text-[var(--text-muted)]">
                {card.label}
              </p>
              <p className="mt-2 text-3xl font-black text-white">
                {card.value}
              </p>
            </div>
          </div>
        ))}
      </div>

      <div className="glass-card space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-white">Request Queue</h2>
            <p className="text-sm text-[var(--text-muted)]">
              Every "make public" action lands here until an admin approves or rejects it.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {FILTERS.map((value) => (
              <button
                key={value}
                onClick={() => setFilter(value)}
                className={`rounded-lg border px-3 py-1.5 text-xs font-bold uppercase tracking-wider ${
                  filter === value
                    ? "border-primary-400 bg-primary-500/10 text-primary-300"
                    : "border-[var(--border)] text-[var(--text-muted)] hover:text-white"
                }`}
              >
                {value.replace("_", " ")}
              </button>
            ))}
          </div>
        </div>

        {error ? (
          <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
            {error}
          </div>
        ) : null}

        {busy && requests.length === 0 ? (
          <div className="rounded-xl border border-[var(--border)] px-4 py-8 text-center text-sm text-[var(--text-muted)]">
            Loading admin queue...
          </div>
        ) : requests.length === 0 ? (
          <div className="rounded-xl border border-[var(--border)] px-4 py-8 text-center text-sm text-[var(--text-muted)]">
            No requests found for this filter.
          </div>
        ) : (
          <div className="space-y-4">
            {requests.map((request) => (
              <div
                key={request.request_id}
                className="rounded-2xl border border-[var(--border)] bg-white/[0.03] p-5"
              >
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="rounded-full border border-primary-500/30 bg-primary-500/10 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-primary-200">
                        {request.asset_type}
                      </span>
                      <span className="rounded-full border border-[var(--border)] px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                        {request.status.replace("_", " ")}
                      </span>
                    </div>
                    <h3 className="mt-3 text-xl font-semibold text-white">
                      {request.asset_name}
                    </h3>
                    <p className="mt-1 text-sm text-[var(--text-muted)]">
                      Requested by {request.requester_name} • {request.affiliation} • {request.institutional_email}
                    </p>
                  </div>
                  <div className="text-right text-xs text-[var(--text-muted)]">
                    <p>Request ID: {request.request_id}</p>
                    <p>Submitted: {formatDate(request.submitted_at)}</p>
                    {request.reviewed_at ? (
                      <p>Reviewed: {formatDate(request.reviewed_at)}</p>
                    ) : null}
                  </div>
                </div>

                <div className="mt-5 grid gap-4 lg:grid-cols-2">
                  <InfoBlock label="Research Title" value={request.research_title} />
                  <InfoBlock label="Research Area" value={request.research_area} />
                  <InfoBlock label="Country" value={request.country} />
                  <InfoBlock label="Owner" value={request.owner_email || request.owner_id || "Not provided"} />
                </div>

                <div className="mt-4 grid gap-4 lg:grid-cols-2">
                  <TextBlock label="Research Summary" value={request.research_summary} />
                  <TextBlock label="Intended Use" value={request.intended_use} />
                </div>

                <div className="mt-4 grid gap-4 lg:grid-cols-2">
                  <TextBlock
                    label="Compliance / Notes"
                    value={[
                      request.confirms_data_rights ? "Confirms sharing rights" : "Missing rights confirmation",
                      request.confirms_no_pii ? "Confirms no PII" : "PII confirmation missing",
                      request.confirms_terms ? "Accepted publication terms" : "Terms not accepted",
                      request.ethics_approval_required
                        ? `Ethics approval: ${request.ethics_approval_reference || "required"}`
                        : "No ethics approval required",
                      request.additional_notes || "No extra notes",
                    ].join("\n")}
                  />
                  <div className="space-y-2 rounded-xl border border-[var(--border)] bg-black/10 p-4">
                    <label className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                      Admin Review Notes
                    </label>
                    <textarea
                      value={notesById[request.request_id] ?? request.review_notes ?? ""}
                      onChange={(e) =>
                        setNotesById((prev) => ({
                          ...prev,
                          [request.request_id]: e.target.value,
                        }))
                      }
                      disabled={request.status !== "pending_review" || busy}
                      className="smiles-input min-h-[132px]"
                      placeholder="Add internal review notes or approval comments..."
                    />
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => onReview(request.request_id, "approved")}
                        disabled={request.status !== "pending_review" || busy}
                        className="inline-flex items-center gap-2 rounded-lg bg-green-600 px-4 py-2 text-sm font-semibold text-white hover:bg-green-500 disabled:opacity-50"
                      >
                        <CheckCircle2 className="h-4 w-4" />
                        Approve
                      </button>
                      <button
                        onClick={() => onReview(request.request_id, "rejected")}
                        disabled={request.status !== "pending_review" || busy}
                        className="inline-flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-500 disabled:opacity-50"
                      >
                        <XCircle className="h-4 w-4" />
                        Reject
                      </button>
                    </div>
                    {request.reviewed_by ? (
                      <p className="text-xs text-[var(--text-muted)]">
                        Reviewed by {request.reviewed_by}
                      </p>
                    ) : null}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {overview?.recent_requests?.length ? (
        <div className="glass-card">
          <div className="mb-4 flex items-center gap-2">
            <Shield className="h-4 w-4 text-primary-300" />
            <h2 className="text-lg font-semibold text-white">Recent Activity</h2>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            {overview.recent_requests.map((request) => (
              <div
                key={request.request_id}
                className="rounded-xl border border-[var(--border)] bg-white/[0.03] p-4"
              >
                <p className="text-sm font-semibold text-white">
                  {request.asset_name}
                </p>
                <p className="mt-1 text-xs text-[var(--text-muted)]">
                  {request.asset_type} • {request.status.replace("_", " ")} • {request.requester_name}
                </p>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function formatDate(value?: string | null) {
  if (!value) return "-";
  return new Date(value).toLocaleString();
}

function InfoBlock({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-black/10 p-4">
      <p className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
        {label}
      </p>
      <p className="mt-2 text-sm text-white">{value}</p>
    </div>
  );
}

function TextBlock({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-black/10 p-4">
      <p className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
        {label}
      </p>
      <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-white">
        {value}
      </p>
    </div>
  );
}
