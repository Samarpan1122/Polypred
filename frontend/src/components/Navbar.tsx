"use client";

import { FlaskConical, Github, Menu } from "lucide-react";

export default function Navbar() {
  return (
    <header className="flex h-14 items-center justify-between border-b border-[var(--border)] bg-[var(--bg-card)] px-6">
      {/* Mobile menu toggle */}
      <button className="md:hidden">
        <Menu className="h-5 w-5 text-[var(--text-muted)]" />
      </button>

      {/* Mobile logo */}
      <div className="flex items-center gap-2 md:hidden">
        <FlaskConical className="h-5 w-5 text-primary-400" />
        <span className="font-bold text-white">CopolPred</span>
      </div>

      {/* Breadcrumb placeholder */}
      <div className="hidden md:block" />

      {/* Actions */}
      <div className="flex items-center gap-3">
        <a
          href="https://github.com"
          target="_blank"
          rel="noopener noreferrer"
          className="text-[var(--text-muted)] hover:text-white"
        >
          <Github className="h-4 w-4" />
        </a>
      </div>
    </header>
  );
}
