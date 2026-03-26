"use client";

import { useState } from "react";
import Link from "next/link";
import { Mail, ArrowRight, ShieldCheck, ArrowLeft } from "lucide-react";
import { useAuth } from "@/lib/contexts/AuthContext";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const { forgotPassword } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await forgotPassword(email);
      setSubmitted(true);
    } catch (err: any) {
      alert(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (submitted) {
    return (
      <div className="flex min-h-[calc(100vh-120px)] items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
        <div className="w-full max-w-md space-y-8 text-center">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-primary-600/10 text-primary-400">
            <Mail className="h-10 w-10" />
          </div>
          <h2 className="text-3xl font-extrabold text-white">
            Check your inbox
          </h2>
          <p className="mt-2 text-[var(--text-muted)]">
            We've sent a password reset link to{" "}
            <span className="text-white font-medium">{email}</span>. Please
            click the link to reset your password.
          </p>
          <div className="pt-6">
            <Link
              href="/login"
              className="text-primary-400 hover:text-primary-300 font-bold flex items-center justify-center gap-2"
            >
              <ArrowLeft className="h-4 w-4" />
              Return to Login
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-[calc(100vh-120px)] items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="w-full max-w-md space-y-8">
        <div className="text-center">
          <h2 className="text-3xl font-extrabold text-white">Reset Password</h2>
          <p className="mt-2 text-sm text-[var(--text-muted)]">
            Enter your account email and we'll send a reset code.
          </p>
        </div>

        <form className="glass-card mt-8 space-y-6" onSubmit={handleSubmit}>
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

          <button
            type="submit"
            disabled={loading}
            className="group relative flex w-full justify-center rounded-lg bg-primary-600 px-4 py-3 text-sm font-semibold text-white hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-all disabled:opacity-50"
          >
            {loading ? "Sending link..." : "Send Reset Link"}
            <ArrowRight className="ml-2 h-4 w-4" />
          </button>

          <div className="text-center">
            <Link
              href="/login"
              className="text-sm font-medium text-[var(--text-muted)] hover:text-white flex items-center justify-center gap-1"
            >
              <ArrowLeft className="h-3 w-3" />
              Back to Sign In
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}
