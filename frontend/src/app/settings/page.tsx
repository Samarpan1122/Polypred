"use client";

import { useAuth } from "@/lib/contexts/AuthContext";
import { User, Building, Mail, Shield, Save, UserCog } from "lucide-react";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

export default function SettingsPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.push("/login");
    }
  }, [user, loading, router]);

  if (loading || !user) return null;

  return (
    <div className="max-w-4xl space-y-8 py-6">
      <div>
        <h1 className="text-3xl font-bold text-white flex items-center gap-3">
            <UserCog className="h-8 w-8 text-primary-400" />
            Account Settings
        </h1>
        <p className="text-[var(--text-muted)] mt-1">
          Manage your researcher profile and security preferences.
        </p>
      </div>

      <div className="grid gap-8 md:grid-cols-3">
        <div className="md:col-span-2 space-y-6">
            <div className="glass-card space-y-6">
                <h3 className="text-sm font-bold text-white uppercase tracking-widest border-b border-[var(--border)] pb-4">Profile Information</h3>
                
                <div className="space-y-4">
                    <div>
                        <label className="block text-xs font-bold text-[var(--text-muted)] uppercase mb-2 ml-1">Full Name</label>
                        <div className="relative">
                            <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[var(--text-muted)]" />
                            <input type="text" defaultValue={user.name} className="smiles-input w-full pl-10" />
                        </div>
                    </div>

                    <div>
                        <label className="block text-xs font-bold text-[var(--text-muted)] uppercase mb-2 ml-1">Email (Institutional)</label>
                        <div className="relative">
                            <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[var(--text-muted)]" />
                            <input type="email" readOnly value={user.email} className="smiles-input w-full pl-10 opacity-70 cursor-not-allowed" />
                        </div>
                    </div>

                    <div>
                        <label className="block text-xs font-bold text-[var(--text-muted)] uppercase mb-2 ml-1">Affiliation</label>
                        <div className="relative">
                            <Building className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[var(--text-muted)]" />
                            <input type="text" defaultValue={user.affiliation} className="smiles-input w-full pl-10" />
                        </div>
                    </div>
                </div>

                <div className="pt-4 flex justify-end">
                    <button className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary-600 hover:bg-primary-700 text-sm font-bold text-white transition-all">
                        <Save className="h-4 w-4" />
                        Save Changes
                    </button>
                </div>
            </div>
        </div>

        <div className="space-y-6">
            <div className="glass-card">
                <h3 className="text-sm font-bold text-white uppercase tracking-widest border-b border-[var(--border)] pb-4">Security</h3>
                <div className="mt-4 space-y-4">
                    <div className="flex items-center gap-3 p-3 rounded-lg bg-white/5 border border-[var(--border)]">
                        <Shield className="h-8 w-8 text-green-400" />
                        <div>
                            <p className="text-xs font-bold text-white uppercase">2FA Enabled</p>
                            <p className="text-[10px] text-[var(--text-muted)]">Verified via Auth0</p>
                        </div>
                    </div>
                    <button className="w-full py-2 text-xs font-bold text-primary-400 hover:text-white transition-colors">Change Password</button>
                </div>
            </div>
        </div>
      </div>
    </div>
  );
}
