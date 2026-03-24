"use client";

import { Users, Mail, ExternalLink, ShieldCheck, Linkedin, Globe } from "lucide-react";

const CONTRIBUTORS = [
  {
    name: "Sabyasachi Mohanty",
    linkedin: "https://www.linkedin.com/in/sabyasachi-mohanty-a0a87a172/",
    website: "https://google.com"
  },
  {
    name: "Samarpan Mohanty",
    linkedin: "https://www.linkedin.com/in/samarpan-mohanty-8b3bb0278/",
    website: "https://google.com"
  },
  {
    name: "Habibollah Safari",
    linkedin: "https://www.linkedin.com/in/mona-bavarian-71895a1a/",
    website: "https://google.com"
  },
  {
    name: "Mona Bavarian",
    role: "Principal Investigator",
    linkedin: "https://www.linkedin.com/in/habib-safari/",
    website: "https://google.com"
  },
];

export default function AboutPage() {
  return (
    <div className="mx-auto max-w-4xl space-y-12 py-8">
      {/* Hero Section */}
      <section className="text-center space-y-4">
        <div className="inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-primary-600/10 text-primary-400 mb-4">
          <Users className="h-8 w-8" />
        </div>
        <h1 className="text-4xl font-bold tracking-tight text-white">About CopolPred</h1>
        <p className="text-lg text-[var(--text-muted)] max-w-2xl mx-auto">
          A state-of-the-art machine learning platform dedicated to advancing copolymerisation research
          through precise reactivity-ratio prediction.
        </p>
      </section>

      {/* Team Section */}
      <section className="space-y-6">
        <div className="flex items-center gap-3 border-b border-[var(--border)] pb-4">
          <ShieldCheck className="h-5 w-5 text-primary-400" />
          <h2 className="text-xl font-semibold text-white">Project Contributors</h2>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          {CONTRIBUTORS.map((person) => (
            <div key={person.name} className="glass-card group hover:border-primary-500/50 transition-all">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="text-lg font-bold text-white group-hover:text-primary-400 transition-colors">
                    {person.name}
                  </h3>
                  {person.role && (
                    <p className="text-sm text-[var(--text-muted)] mt-1">{person.role}</p>
                  )}
                </div>
                <div className="flex gap-2">
                  <a
                    href={person.linkedin}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="p-1.5 rounded-md hover:bg-primary-600/10 text-[var(--text-muted)] hover:text-white transition-all"
                  >
                    <Linkedin className="h-4 w-4" />
                  </a>
                  <a
                    href={person.website}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="p-1.5 rounded-md hover:bg-primary-600/10 text-[var(--text-muted)] hover:text-white transition-all"
                  >
                    <Globe className="h-4 w-4" />
                  </a>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Mission Section */}
      <section className="glass-card bg-primary-600/5 border-primary-500/20">
        <h2 className="text-xl font-semibold text-white mb-4">Our Mission</h2>
        <p className="text-[var(--text-muted)] leading-relaxed">
          CopolPred aims to bridge the gap between complex chemical data and actionable insights
          using advanced deep learning architectures. By providing a unified interface for
          data processing, model training, and inference, we empower researchers to predict
          polymer properties with unprecedented accuracy and speed.The goal is not to develop a standalone tool, but to serve as an assistive framework for experimentalists, enabling more efficient candidate filtering and decision-making, not replacing human expertise but supporting it.
        </p>
      </section>

      {/* Footer Info */}
      <footer className="text-center pt-8 border-t border-[var(--border)]">
        <p className="text-sm text-[var(--text-muted)]">
          Developed for the advanced chemical modeling community.
        </p>
      </footer>
    </div>
  );
}
