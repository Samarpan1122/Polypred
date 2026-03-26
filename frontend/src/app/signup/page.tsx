"use client";

import { useState } from "react";
import Link from "next/link";
import {
  ShieldCheck,
  Users,
  Mail,
  Building,
  Lock,
  ArrowRight,
} from "lucide-react";
import { useAuth } from "@/lib/contexts/AuthContext";
import { useRouter } from "next/navigation";

export default function SignupPage() {
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const { signup, confirmSignup } = useAuth();
  const router = useRouter();

  // Form input states
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [affiliation, setAffiliation] = useState("");
  const [password, setPassword] = useState("");

  // Verification states
  const [verificationCode, setVerificationCode] = useState("");
  const [verifying, setVerifying] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await signup({ email, password, name, affiliation });
      setSubmitted(true);
    } catch (err: any) {
      alert(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    setVerifying(true);
    try {
      await confirmSignup(email, verificationCode);
      router.push("/login"); // Redirect to login after successful verification
    } catch (err: any) {
      alert(err.message);
    } finally {
      setVerifying(false);
    }
  };

  if (submitted) {
    return (
      <div className="flex min-h-[calc(100vh-120px)] items-center justify-center p-4">
        <div className="glass-card w-full max-w-md space-y-6 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-primary-600/20 text-primary-400">
            <Mail className="h-6 w-6" />
          </div>
          <h2 className="text-2xl font-bold text-white">Check your inbox</h2>
          <p className="break-words text-[var(--text-muted)]">
            We've sent a verification link to{" "}
            <strong className="break-all">{email}</strong>. Please enter the
            code below to verify your account.
          </p>

          <form onSubmit={handleVerify} className="space-y-4">
            <input
              type="text"
              required
              value={verificationCode}
              onChange={(e) => setVerificationCode(e.target.value)}
              placeholder="Enter 6-digit code"
              className="smiles-input w-full text-center tracking-widest text-lg font-bold"
              maxLength={6}
            />
            <button
              type="submit"
              disabled={verifying}
              className="w-full rounded-lg bg-primary-600 px-4 py-3 text-sm font-bold text-white hover:bg-primary-700 transition-all disabled:opacity-50"
            >
              {verifying ? "Verifying..." : "Confirm Verification"}
            </button>
          </form>

          <p className="text-xs text-[var(--text-muted)]">
            Didn't receive the email? Check your spam folder and try again.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-[calc(100vh-120px)] items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="w-full max-w-md space-y-6 sm:space-y-8">
        <div className="text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-primary-600/10 text-primary-400">
            <ShieldCheck className="h-8 w-8" />
          </div>
          <h2 className="mt-6 text-3xl font-extrabold text-white">
            Create your account
          </h2>
          <p className="mt-2 text-sm text-[var(--text-muted)]">
            Sign up to securely store data and run predictions.
          </p>
        </div>

        <form
          className="glass-card mt-8 space-y-6 glow-blue transition-all"
          onSubmit={handleSubmit}
        >
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] ml-1 mb-1.5">
                Full Name
              </label>
              <div className="relative">
                <Users className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--text-muted)]" />
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="John Doe"
                  className="smiles-input w-full pl-11"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] ml-1 mb-1.5">
                Email Address
              </label>
              <div className="relative">
                <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--text-muted)]" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@example.com"
                  className="smiles-input w-full pl-11"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] ml-1 mb-1.5">
                Affiliation
              </label>
              <div className="relative">
                <Building className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--text-muted)]" />
                <input
                  type="text"
                  required
                  value={affiliation}
                  onChange={(e) => setAffiliation(e.target.value)}
                  placeholder="University of Waterloo"
                  className="smiles-input w-full pl-11"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)] ml-1 mb-1.5">
                Secure Password
              </label>
              <div className="relative">
                <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--text-muted)]" />
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="smiles-input w-full pl-11"
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
            <span className="text-[var(--text-muted)]">
              Already have an account?{" "}
            </span>
            <Link
              href="/login"
              className="font-medium text-primary-400 hover:text-primary-300"
            >
              Log in
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}
