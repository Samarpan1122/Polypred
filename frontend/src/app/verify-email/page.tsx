"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { CheckCircle2, XCircle, Loader2 } from "lucide-react";
import Link from "next/link";
import { useAuth } from "@/lib/contexts/AuthContext";

function VerifyEmailContent() {
  const [status, setStatus] = useState<"loading" | "success" | "error">(
    "loading",
  );
  const [errorMessage, setErrorMessage] = useState(
    "The verification link is invalid or has expired.",
  );
  const searchParams = useSearchParams();
  const { confirmSignup } = useAuth();
  const code = searchParams.get("code") || searchParams.get("token") || "";
  const email = searchParams.get("email") || searchParams.get("username") || "";

  useEffect(() => {
    if (!email || !code) {
      setStatus("error");
      setErrorMessage("Missing email or code in the verification link.");
      return;
    }

    const run = async () => {
      try {
        await confirmSignup(email, code);
        setStatus("success");
      } catch (err: any) {
        setStatus("error");
        setErrorMessage(
          err?.message || "Verification failed. Please try again.",
        );
      }
    };

    run();
  }, [email, code, confirmSignup]);

  return (
    <div className="flex min-h-[calc(100vh-120px)] items-center justify-center p-4">
      <div className="glass-card max-w-md w-full text-center space-y-6 py-12">
        {status === "loading" && (
          <>
            <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-primary-600/10 text-primary-400">
              <Loader2 className="h-10 w-10 animate-spin" />
            </div>
            <h2 className="text-2xl font-bold text-white">
              Verifying your account
            </h2>
            <p className="text-[var(--text-muted)]">
              Confirming your email address...
            </p>
          </>
        )}

        {status === "success" && (
          <>
            <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-green-600/10 text-green-400">
              <CheckCircle2 className="h-10 w-10" />
            </div>
            <h2 className="text-2xl font-bold text-white">Email Verified!</h2>
            <p className="text-[var(--text-muted)]">
              Your account is now verified. You can sign in and continue.
            </p>
            <div className="pt-4">
              <Link
                href="/login"
                className="inline-flex items-center justify-center rounded-lg bg-primary-600 px-6 py-3 text-sm font-bold text-white hover:bg-primary-700 transition-all"
              >
                Continue to Login
              </Link>
            </div>
          </>
        )}

        {status === "error" && (
          <>
            <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-red-600/10 text-red-400">
              <XCircle className="h-10 w-10" />
            </div>
            <h2 className="text-2xl font-bold text-white">
              Verification Failed
            </h2>
            <p className="text-[var(--text-muted)]">{errorMessage}</p>
            <div className="pt-4">
              <Link
                href="/signup"
                className="text-primary-400 hover:text-white font-bold transition-all"
              >
                Back to Sign up
              </Link>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-[calc(100vh-120px)] items-center justify-center">
          <div className="text-primary-400 animate-pulse font-bold tracking-widest uppercase">
            Validating Certificate...
          </div>
        </div>
      }
    >
      <VerifyEmailContent />
    </Suspense>
  );
}
