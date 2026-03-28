"use client";

import React, { createContext, useContext, useState, useEffect } from "react";
import { useRouter } from "next/navigation";

interface User {
  id: string;
  name: string;
  email: string;
  affiliation: string;
  isAdmin?: boolean;
}

const ADMIN_EMAILS = (process.env.NEXT_PUBLIC_ADMIN_EMAILS ||
  "smohanty13@huskers.unl.edu")
  .split(",")
  .map((email) => email.trim().toLowerCase())
  .filter(Boolean);

const normalizeUser = (user: Partial<User> & { email?: string }) => {
  const email = user.email || "";
  return {
    ...user,
    id: user.id || email || "anonymous",
    email,
    name: user.name || email.split("@")[0] || "user",
    affiliation: user.affiliation || "Independent",
    isAdmin: ADMIN_EMAILS.includes(email.toLowerCase()),
  } as User;
};

const getErrorMessage = async (res: Response, fallback: string) => {
  try {
    const data = await res.json();
    return data?.detail || fallback;
  } catch {
    return fallback;
  }
};

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (userData: any) => Promise<void>;
  confirmSignup: (email: string, code: string) => Promise<void>;
  forgotPassword: (email: string) => Promise<void>;
  resetPassword: (
    email: string,
    code: string,
    newPass: string,
  ) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const getApiBase = () => {
  if (process.env.NEXT_PUBLIC_API_URL)
    return `${process.env.NEXT_PUBLIC_API_URL}/api/auth`;
  if (typeof window !== "undefined") {
    const isLocal =
      window.location.hostname === "localhost" ||
      window.location.hostname === "127.0.0.1";
    if (isLocal && window.location.port === "3000")
      return "http://localhost:8000/api/auth";
  }
  return "/api/auth";
};
const API_BASE = getApiBase();

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    const savedUser = localStorage.getItem("polypred_user");
    if (savedUser) {
      const parsed = JSON.parse(savedUser);
      const normalized = normalizeUser(parsed);
      setUser(normalized);
      localStorage.setItem("polypred_user", JSON.stringify(normalized));
    }
    setLoading(false);
  }, []);

  const login = async (email: string, password: string) => {
    const res = await fetch(`${API_BASE}/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });

    if (!res.ok) {
      throw new Error(await getErrorMessage(res, "Login failed"));
    }

    await res.json();
    // Assuming data contains AuthenticationResult (IdToken, etc)
    // We'll store a mock user derived from email for now
    const userData = normalizeUser({
      id: email,
      email,
      name: email.split("@")[0],
      affiliation: "Independent",
    });
    setUser(userData);
    localStorage.setItem("polypred_user", JSON.stringify(userData));
    router.push("/");
  };

  const signup = async (userData: any) => {
    const res = await fetch(`${API_BASE}/signup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(userData),
    });

    if (!res.ok) {
      throw new Error(await getErrorMessage(res, "Signup failed"));
    }
  };

  const confirmSignup = async (email: string, code: string) => {
    const res = await fetch(`${API_BASE}/confirm-signup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, code }),
    });

    if (!res.ok) {
      throw new Error(await getErrorMessage(res, "Verification failed"));
    }
    router.push("/login");
  };

  const forgotPassword = async (email: string) => {
    const res = await fetch(`${API_BASE}/forgot-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });

    if (!res.ok) {
      throw new Error(await getErrorMessage(res, "Request failed"));
    }
  };

  const resetPassword = async (
    email: string,
    code: string,
    new_password: string,
  ) => {
    const res = await fetch(`${API_BASE}/reset-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, code, new_password }),
    });

    if (!res.ok) {
      throw new Error(await getErrorMessage(res, "Reset failed"));
    }
    router.push("/login");
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem("polypred_user");
    router.push("/login");
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        login,
        signup,
        confirmSignup,
        forgotPassword,
        resetPassword,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
