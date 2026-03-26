"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/contexts/AuthContext";
import {
  FlaskConical,
  LayoutDashboard,
  Beaker,
  GitCompare,
  Cpu,
  Upload,
  FolderOpen,
  Layers,
  Dumbbell,
  BarChart3,
  FlaskRound,
  Info,
  LogOut,
  LogIn,
} from "lucide-react";

const NAV_ITEMS = [
  { label: "Dashboard", href: "/", icon: LayoutDashboard },
  { label: "Upload Data", href: "/upload", icon: Upload },
  { label: "My Files", href: "/my-storage", icon: FolderOpen },
  { label: "Training", href: "/training", icon: Dumbbell },
  { label: "Results", href: "/results", icon: BarChart3 },
  { label: "Predict", href: "/predict", icon: Beaker },
  { label: "Models", href: "/models", icon: Cpu },
];

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();

  return (
    <aside className="hidden w-64 flex-shrink-0 border-r border-[var(--border)] bg-[var(--bg-card)] md:flex md:flex-col">
      {/* Logo */}
      <div className="flex items-center gap-3 border-b border-[var(--border)] px-6 py-5">
        <FlaskConical className="h-8 w-8 text-primary-400" />
        <div>
          <h1 className="text-lg font-bold tracking-tight text-white">
            CopolPred
          </h1>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 px-3 py-4">
        <p className="px-3 pb-1 pt-2 text-[10px] uppercase tracking-wider text-[var(--text-muted)]">
          Experiment
        </p>
        {NAV_ITEMS.slice(0, 4).map((item) => {
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                active
                  ? "bg-primary-600/20 text-primary-400"
                  : "text-[var(--text-muted)] hover:bg-[var(--bg-hover)] hover:text-white",
              )}
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
        <p className="px-3 pb-1 pt-4 text-[10px] uppercase tracking-wider text-[var(--text-muted)]">
          Inference
        </p>
        {NAV_ITEMS.slice(4).map((item) => {
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                active
                  ? "bg-primary-600/20 text-primary-400"
                  : "text-[var(--text-muted)] hover:bg-[var(--bg-hover)] hover:text-white",
              )}
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="mt-auto border-t border-[var(--border)] p-4 flex flex-col gap-2">
        <Link
          href="/about"
          className={cn(
            "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
            pathname === "/about"
              ? "bg-primary-600/20 text-primary-400"
              : "text-[var(--text-muted)] hover:bg-[var(--bg-hover)] hover:text-white",
          )}
        >
          <Info className="h-4 w-4" />
          About Us
        </Link>
        <div className="h-px w-full bg-[var(--border)] my-2"></div>
        {user ? (
          <div className="flex items-center justify-between px-3 py-2">
            <div className="flex items-center gap-3 overflow-hidden">
              <div className="h-8 w-8 rounded-full bg-primary-600/20 flex items-center justify-center text-primary-400 font-bold shrink-0">
                {user.name ? user.name.charAt(0) : "U"}
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-xs font-bold text-white truncate">
                  {user.name}
                </p>
                <p className="text-[10px] text-[var(--text-muted)] truncate">
                  {user.affiliation}
                </p>
              </div>
            </div>
            <button
              onClick={() => {
                logout();
                router.push("/login");
              }}
              className="p-1.5 rounded-lg hover:bg-red-500/10 text-[var(--text-muted)] hover:text-red-400 transition-colors"
              title="Logout"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        ) : (
          <Link
            href="/login"
            className={cn(
              "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
              pathname === "/login"
                ? "bg-primary-600/20 text-primary-400"
                : "text-[var(--text-muted)] hover:bg-[var(--bg-hover)] hover:text-white",
            )}
          >
            <LogIn className="h-4 w-4" />
            Log In
          </Link>
        )}
      </div>
    </aside>
  );
}
