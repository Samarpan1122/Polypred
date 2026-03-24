"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  FlaskConical,
  LayoutDashboard,
  Beaker,
  GitCompare,
  Cpu,
  Upload,
  Layers,
  Dumbbell,
  BarChart3,
  FlaskRound,
  Info,
} from "lucide-react";

const NAV_ITEMS = [
  { label: "Dashboard", href: "/", icon: LayoutDashboard },
  { label: "Upload Data", href: "/upload", icon: Upload },
  { label: "Training", href: "/training", icon: Dumbbell },
  { label: "Results", href: "/results", icon: BarChart3 },
  { label: "Predict", href: "/predict", icon: Beaker },
  { label: "Models", href: "/models", icon: Cpu },
];

export default function Sidebar() {
  const pathname = usePathname();

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
      <div className="mt-auto border-t border-[var(--border)] p-4">
        <Link
          href="/about"
          className={cn(
            "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
            pathname === "/about"
              ? "bg-primary-600/20 text-primary-400"
              : "text-[var(--text-muted)] hover:bg-[var(--bg-hover)] hover:text-white"
          )}
        >
          <Info className="h-4 w-4" />
          About Us
        </Link>
      </div>
    </aside>
  );
}
