"use client";

import { useState } from "react";
import Link from "next/link";
import { Lock, Mail, ArrowRight, ShieldCheck } from "lucide-react";
import { useAuth } from "@/lib/contexts/AuthContext";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const [loading, setLoading] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const { login } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await login(email, password);
    } catch (err: any) {
      alert(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-[calc(100vh-120px)] items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="w-full max-w-md space-y-8">
        <div className="text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-primary-600/10 text-primary-400">
            <Lock className="h-8 w-8" />
          </div>
          <h2 className="mt-6 text-3xl font-extrabold text-white">
            Welcome back
          </h2>
          <p className="mt-2 text-sm text-[var(--text-muted)]">
            Sign in to access your workspace and predictions.
          </p>
        </div>

        <form
          className="glass-card mt-8 space-y-6 glow-blue transition-all"
          onSubmit={handleSubmit}
        >
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] ml-1 mb-1.5">
                Email Address
              </label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--text-muted)]" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@example.com"
                  className="smiles-input w-full pl-10"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] ml-1 mb-1.5">
                Password
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--text-muted)]" />
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="smiles-input w-full pl-10"
                />
              </div>
            </div>
          </div>

          <div className="flex items-center justify-end">
            <Link
              href="/forgot-password"
              title="Forgot password"
              className="text-xs font-medium text-primary-400 hover:text-primary-300"
            >
              Forgot password?
            </Link>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="group relative flex w-full justify-center rounded-lg bg-primary-600 px-4 py-3 text-sm font-semibold text-white hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-all disabled:opacity-50"
          >
            {loading ? "Authenticating..." : "Login"}
            <ArrowRight className="ml-2 h-4 w-4 transition-transform group-hover:translate-x-1" />
          </button>

          <div className="text-center text-sm">
            <span className="text-[var(--text-muted)]">Need an account? </span>
            <Link
              href="/signup"
              className="font-medium text-primary-400 hover:text-primary-300"
            >
              Create an account
            </Link>
          </div>

          <div className="mt-4 flex items-center justify-center gap-2 border-t border-[var(--border)] pt-4">
            <ShieldCheck className="h-4 w-4 text-primary-400" />
            <span className="text-[10px] text-[var(--text-muted)] uppercase tracking-widest font-bold">
              KMS AES-256 Encrypted Session
            </span>
          </div>
        </form>
      </div>
    </div>
  );
}
