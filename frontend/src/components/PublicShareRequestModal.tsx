"use client";

import { useEffect, useState } from "react";
import { X, Globe2, Send } from "lucide-react";
import { submitPublicShareRequest } from "@/lib/api";
import type {
  PublicShareAssetType,
  PublicShareRequestPayload,
} from "@/lib/types";
import { useAuth } from "@/lib/contexts/AuthContext";

interface PublicShareRequestModalProps {
  isOpen: boolean;
  assetType: PublicShareAssetType;
  assetId: string;
  assetName: string;
  ownerId?: string;
  ownerEmail?: string;
  onClose: () => void;
}

const initialForm = {
  requester_name: "",
  institutional_email: "",
  affiliation: "",
  department: "",
  position_title: "",
  university_id: "",
  orcid: "",
  country: "",
  profile_url: "",
  research_title: "",
  research_area: "",
  research_summary: "",
  intended_use: "",
  funding_source: "",
  is_external_research_data: false,
  external_data_source: "",
  external_data_license: "",
  citation_text: "",
  ethics_approval_required: false,
  ethics_approval_reference: "",
  confirms_data_rights: false,
  confirms_no_pii: false,
  confirms_terms: false,
  additional_notes: "",
};

export default function PublicShareRequestModal({
  isOpen,
  assetType,
  assetId,
  assetName,
  ownerId,
  ownerEmail,
  onClose,
}: PublicShareRequestModalProps) {
  const { user } = useAuth();
  const [form, setForm] = useState(initialForm);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    if (!isOpen) return;
    setForm((prev) => ({
      ...prev,
      requester_name: user?.name || prev.requester_name,
      institutional_email: user?.email || prev.institutional_email,
      affiliation: user?.affiliation || prev.affiliation,
    }));
    setError("");
    setSuccess("");
  }, [isOpen, user]);

  if (!isOpen) return null;

  const update = (key: keyof typeof form, value: string | boolean) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    setSubmitting(true);

    try {
      const payload: PublicShareRequestPayload = {
        asset_type: assetType,
        asset_id: assetId,
        asset_name: assetName,
        owner_id: ownerId || user?.id || "",
        owner_email: ownerEmail || user?.email || "",
        requester_name: form.requester_name,
        institutional_email: form.institutional_email,
        affiliation: form.affiliation,
        department: form.department,
        position_title: form.position_title,
        university_id: form.university_id,
        orcid: form.orcid,
        country: form.country,
        profile_url: form.profile_url,
        research_title: form.research_title,
        research_area: form.research_area,
        research_summary: form.research_summary,
        intended_use: form.intended_use,
        funding_source: form.funding_source,
        is_external_research_data: form.is_external_research_data,
        external_data_source: form.external_data_source,
        external_data_license: form.external_data_license,
        citation_text: form.citation_text,
        ethics_approval_required: form.ethics_approval_required,
        ethics_approval_reference: form.ethics_approval_reference,
        confirms_data_rights: form.confirms_data_rights,
        confirms_no_pii: form.confirms_no_pii,
        confirms_terms: form.confirms_terms,
        additional_notes: form.additional_notes,
      };

      const res = await submitPublicShareRequest(payload);
      setSuccess(`Request submitted. Tracking ID: ${res.request_id}`);
      setForm(initialForm);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to submit request");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      onClick={onClose}
    >
      <div
        className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-2xl border border-[var(--border)] bg-[var(--bg-card)] p-5"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <h2 className="flex items-center gap-2 text-lg font-semibold text-white">
              <Globe2 className="h-5 w-5 text-primary-400" />
              Make {assetType === "dataset" ? "Dataset" : "Model"} Public
            </h2>
            <p className="mt-1 text-xs text-[var(--text-muted)]">
              Asset: <span className="text-white">{assetName}</span> ({assetId})
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-2 text-[var(--text-muted)] hover:bg-[var(--bg-hover)] hover:text-white"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <form onSubmit={onSubmit} className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Full name" required>
              <input
                className="smiles-input"
                value={form.requester_name}
                onChange={(e) => update("requester_name", e.target.value)}
                required
              />
            </Field>
            <Field label="Institutional email" required>
              <input
                type="email"
                className="smiles-input"
                value={form.institutional_email}
                onChange={(e) => update("institutional_email", e.target.value)}
                required
              />
            </Field>
            <Field label="Affiliation" required>
              <input
                className="smiles-input"
                value={form.affiliation}
                onChange={(e) => update("affiliation", e.target.value)}
                required
              />
            </Field>
            <Field label="Department">
              <input
                className="smiles-input"
                value={form.department}
                onChange={(e) => update("department", e.target.value)}
              />
            </Field>
            <Field label="Position title">
              <input
                className="smiles-input"
                value={form.position_title}
                onChange={(e) => update("position_title", e.target.value)}
              />
            </Field>
            <Field label="University ID">
              <input
                className="smiles-input"
                value={form.university_id}
                onChange={(e) => update("university_id", e.target.value)}
              />
            </Field>
            <Field label="ORCID">
              <input
                className="smiles-input"
                value={form.orcid}
                onChange={(e) => update("orcid", e.target.value)}
              />
            </Field>
            <Field label="Country" required>
              <input
                className="smiles-input"
                value={form.country}
                onChange={(e) => update("country", e.target.value)}
                required
              />
            </Field>
          </div>

          <Field label="Research profile URL">
            <input
              className="smiles-input"
              value={form.profile_url}
              onChange={(e) => update("profile_url", e.target.value)}
              placeholder="https://..."
            />
          </Field>

          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Research title" required>
              <input
                className="smiles-input"
                value={form.research_title}
                onChange={(e) => update("research_title", e.target.value)}
                required
              />
            </Field>
            <Field label="Research area" required>
              <input
                className="smiles-input"
                value={form.research_area}
                onChange={(e) => update("research_area", e.target.value)}
                required
              />
            </Field>
          </div>

          <Field label="Research summary" required>
            <textarea
              className="smiles-input min-h-[90px]"
              value={form.research_summary}
              onChange={(e) => update("research_summary", e.target.value)}
              required
            />
          </Field>

          <Field label="Intended public use" required>
            <textarea
              className="smiles-input min-h-[90px]"
              value={form.intended_use}
              onChange={(e) => update("intended_use", e.target.value)}
              required
            />
          </Field>

          <Field label="Funding source">
            <input
              className="smiles-input"
              value={form.funding_source}
              onChange={(e) => update("funding_source", e.target.value)}
            />
          </Field>

          <div className="rounded-lg border border-[var(--border)] p-3">
            <label className="flex items-center gap-2 text-sm text-white">
              <input
                type="checkbox"
                checked={form.is_external_research_data}
                onChange={(e) =>
                  update("is_external_research_data", e.target.checked)
                }
              />
              Uses data sourced from outside your own research group
            </label>
            {form.is_external_research_data && (
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <Field label="External data source" required>
                  <input
                    className="smiles-input"
                    value={form.external_data_source}
                    onChange={(e) =>
                      update("external_data_source", e.target.value)
                    }
                    required
                  />
                </Field>
                <Field label="External data license" required>
                  <input
                    className="smiles-input"
                    value={form.external_data_license}
                    onChange={(e) =>
                      update("external_data_license", e.target.value)
                    }
                    required
                  />
                </Field>
                <Field label="Citation / DOI">
                  <input
                    className="smiles-input"
                    value={form.citation_text}
                    onChange={(e) => update("citation_text", e.target.value)}
                  />
                </Field>
              </div>
            )}
          </div>

          <div className="rounded-lg border border-[var(--border)] p-3">
            <label className="flex items-center gap-2 text-sm text-white">
              <input
                type="checkbox"
                checked={form.ethics_approval_required}
                onChange={(e) =>
                  update("ethics_approval_required", e.target.checked)
                }
              />
              This sharing requires ethics/IRB approval
            </label>
            {form.ethics_approval_required && (
              <Field label="Ethics approval reference" required>
                <input
                  className="smiles-input mt-2"
                  value={form.ethics_approval_reference}
                  onChange={(e) =>
                    update("ethics_approval_reference", e.target.value)
                  }
                  required
                />
              </Field>
            )}
          </div>

          <div className="space-y-2 rounded-lg border border-[var(--border)] p-3">
            <label className="flex items-start gap-2 text-sm text-white">
              <input
                type="checkbox"
                checked={form.confirms_data_rights}
                onChange={(e) =>
                  update("confirms_data_rights", e.target.checked)
                }
                required
              />
              I confirm I have legal rights/permission to share this asset.
            </label>
            <label className="flex items-start gap-2 text-sm text-white">
              <input
                type="checkbox"
                checked={form.confirms_no_pii}
                onChange={(e) => update("confirms_no_pii", e.target.checked)}
                required
              />
              I confirm no personally identifiable or restricted human data is
              included.
            </label>
            <label className="flex items-start gap-2 text-sm text-white">
              <input
                type="checkbox"
                checked={form.confirms_terms}
                onChange={(e) => update("confirms_terms", e.target.checked)}
                required
              />
              I agree to the platform's review process and publication terms.
            </label>
          </div>

          <Field label="Additional notes">
            <textarea
              className="smiles-input min-h-[80px]"
              value={form.additional_notes}
              onChange={(e) => update("additional_notes", e.target.value)}
            />
          </Field>

          {error && <p className="text-sm text-red-400">{error}</p>}
          {success && <p className="text-sm text-green-400">{success}</p>}

          <div className="flex items-center justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm text-[var(--text-muted)] hover:text-white"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="inline-flex items-center gap-2 rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-500 disabled:opacity-50"
            >
              <Send className="h-4 w-4" />
              {submitting ? "Submitting..." : "Submit for review"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function Field({
  label,
  children,
  required,
}: {
  label: string;
  children: React.ReactNode;
  required?: boolean;
}) {
  return (
    <label className="block space-y-1">
      <span className="text-xs text-[var(--text-muted)]">
        {label} {required ? <span className="text-red-400">*</span> : null}
      </span>
      {children}
    </label>
  );
}
