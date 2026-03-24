"use client";

import { useState } from "react";
import Link from "next/link";
import { FlaskConical, Lock, Mail, Users, Building, ArrowRight, ShieldCheck } from "lucide-react";

export default function SignupPage() {
  const [loading, setLoading] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    // Submit logic...
  };

  return (
    <div className="flex min-h-[calc(100vh-120px)] items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="w-full max-w-md space-y-8">
        <div className="text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-primary-600/10 text-primary-400">
            <ShieldCheck className="h-8 w-8" />
          </div>
          <h2 className="mt-6 text-3xl font-extrabold text-white">Academic Registration</h2>
          <p className="mt-2 text-sm text-[var(--text-muted)]">
            Create an account to securely store and encrypt your research data.
          </p>
        </div>

        <form className="glass-card mt-8 space-y-6" onSubmit={handleSubmit}>
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] ml-1 mb-1.5">
                Full Name
              </label>
              <div className="relative">
                <Users className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--text-muted)]" />
                <input
                  type="text"
                  required
                  placeholder="John Doe"
                  className="smiles-input w-full pl-10"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] ml-1 mb-1.5">
                Professional/Academic Email
              </label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--text-muted)]" />
                <input
                  type="email"
                  required
                  placeholder="name@university.edu"
                  className="smiles-input w-full pl-10"
                />
              </div>
              <p className="mt-1.5 text-[10px] text-amber-400 flex items-center gap-1 px-1">
                <Lock className="h-3 w-3" />
                Institutional verification required (ApyHub validated)
              </p>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] ml-1 mb-1.5">
                Affiliation
              </label>
              <div className="relative">
                <Building className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--text-muted)]" />
                <input
                  type="text"
                  required
                  placeholder="University of Waterloo"
                  className="smiles-input w-full pl-10"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] ml-1 mb-1.5">
                Secure Password
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--text-muted)]" />
                <input
                  type="password"
                  required
                  placeholder="••••••••"
                  className="smiles-input w-full pl-10"
                />
              </div>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="group relative flex w-full justify-center rounded-lg bg-primary-600 px-4 py-3 text-sm font-semibold text-white hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-all disabled:opacity-50"
          >
            {loading ? "Verifying..." : "Register Now"}
            <ArrowRight className="ml-2 h-4 w-4 transition-transform group-hover:translate-x-1" />
          </button>

          <div className="text-center text-sm">
            <span className="text-[var(--text-muted)]">Already have an account? </span>
            <Link href="/login" className="font-medium text-primary-400 hover:text-primary-300">
              Log in
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}
