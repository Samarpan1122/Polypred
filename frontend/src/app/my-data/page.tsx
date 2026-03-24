"use client";

import { useState } from "react";
import { 
  Database, 
  FileText, 
  Lock, 
  Globe, 
  Trash2, 
  Download, 
  Plus, 
  Share2,
  AlertCircle 
} from "lucide-react";

export default function MyDataPage() {
  const [showPublicForm, setShowPublicForm] = useState(false);
  const [selectedItem, setSelectedItem] = useState(null);

  // Mock data for UI demonstration
  const [data, setData] = useState([
    { id: 1, name: "Copolymer_Dataset_v1.csv", type: "dataset", isPublic: false, date: "2024-03-20" },
    { id: 2, name: "Siamese_LSTM_Weights.pt", type: "model", isPublic: true, date: "2024-03-22" },
  ]);

  return (
    <div className="space-y-8 py-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">My Secure Storage</h1>
          <p className="text-[var(--text-muted)] mt-1">
            Manage your KMS-encrypted datasets and models.
          </p>
        </div>
        <button className="flex items-center gap-2 rounded-lg bg-primary-600 px-4 py-2 text-sm font-semibold text-white hover:bg-primary-700 transition-all">
          <Plus className="h-4 w-4" />
          Upload New
        </button>
      </div>

      {/* Stats Overview */}
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="glass-card flex items-center gap-4">
          <div className="h-10 w-10 rounded-lg bg-primary-600/10 flex items-center justify-center text-primary-400">
            <Lock className="h-5 w-5" />
          </div>
          <div>
            <p className="text-xs text-[var(--text-muted)] uppercase font-bold tracking-tighter">Private Assets</p>
            <p className="text-xl font-bold text-white">12</p>
          </div>
        </div>
        <div className="glass-card flex items-center gap-4">
          <div className="h-10 w-10 rounded-lg bg-green-600/10 flex items-center justify-center text-green-400">
            <Globe className="h-5 w-5" />
          </div>
          <div>
            <p className="text-xs text-[var(--text-muted)] uppercase font-bold tracking-tighter">Public Contributions</p>
            <p className="text-xl font-bold text-white">2</p>
          </div>
        </div>
      </div>

      {/* Data Table */}
      <div className="glass-card p-0 overflow-hidden">
        <table className="w-full text-left">
          <thead>
            <tr className="border-b border-[var(--border)] bg-white/5">
              <th className="px-6 py-4 text-xs font-semibold uppercase text-[var(--text-muted)]">Name</th>
              <th className="px-6 py-4 text-xs font-semibold uppercase text-[var(--text-muted)]">Privacy</th>
              <th className="px-6 py-4 text-xs font-semibold uppercase text-[var(--text-muted)]">Type</th>
              <th className="px-6 py-4 text-xs font-semibold uppercase text-[var(--text-muted)]">Date</th>
              <th className="px-6 py-4 text-xs font-semibold uppercase text-[var(--text-muted)] text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border)]">
            {data.map((item) => (
              <tr key={item.id} className="group hover:bg-white/5 transition-colors">
                <td className="px-6 py-4">
                  <div className="flex items-center gap-3">
                    <FileText className="h-4 w-4 text-primary-400" />
                    <span className="text-sm font-medium text-white">{item.name}</span>
                  </div>
                </td>
                <td className="px-6 py-4">
                  {item.isPublic ? (
                    <span className="inline-flex items-center gap-1 rounded-full bg-green-500/10 px-2 py-0.5 text-[10px] font-bold text-green-400 uppercase">
                      <Globe className="h-3 w-3" /> Public
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] font-bold text-amber-400 uppercase">
                      <Lock className="h-3 w-3" /> Encrypted
                    </span>
                  )}
                </td>
                <td className="px-6 py-4 text-xs text-[var(--text-muted)] capitalize">{item.type}</td>
                <td className="px-6 py-4 text-xs text-[var(--text-muted)]">{item.date}</td>
                <td className="px-6 py-4 text-right">
                  <div className="flex items-center justify-end gap-2">
                    {!item.isPublic && (
                      <button 
                        onClick={() => { setSelectedItem(item); setShowPublicForm(true); }}
                        className="p-1.5 rounded hover:bg-white/10 text-[var(--text-muted)] hover:text-white"
                      >
                        <Share2 className="h-4 w-4" />
                      </button>
                    )}
                    <button className="p-1.5 rounded hover:bg-white/10 text-[var(--text-muted)] hover:text-white">
                      <Download className="h-4 w-4" />
                    </button>
                    <button className="p-1.5 rounded hover:bg-red-500/10 text-[var(--text-muted)] hover:text-red-400">
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Public Share Modal */}
      {showPublicForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="glass-card max-w-lg w-full p-8 space-y-6">
            <div className="flex items-center gap-3">
              <Globe className="h-6 w-6 text-primary-400" />
              <h2 className="text-xl font-bold text-white">Make Data Public</h2>
            </div>
            <p className="text-sm text-[var(--text-muted)] bg-primary-600/10 p-3 rounded-lg border border-primary-500/20">
              <AlertCircle className="h-4 w-4 inline mr-2 align-text-bottom" />
              Making this asset public allows other researchers to cite your work. This action cannot be easily undone.
            </p>
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-[var(--text-muted)] uppercase mb-1.5">Description</label>
                <textarea 
                  className="smiles-input w-full min-h-[100px]" 
                  placeholder="Explain the technical details of this dataset/model..."
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-[var(--text-muted)] uppercase mb-1.5">Paper DOI (Optional)</label>
                <input type="text" className="smiles-input w-full" placeholder="10.1038/s41586-020-2012-7" />
              </div>
            </div>
            <div className="flex gap-3 justify-end mt-8">
              <button 
                onClick={() => setShowPublicForm(false)}
                className="px-4 py-2 rounded-lg hover:bg-white/5 text-sm font-semibold text-white transition-all"
              >
                Cancel
              </button>
              <button className="px-4 py-2 rounded-lg bg-primary-600 hover:bg-primary-700 text-sm font-semibold text-white transition-all">
                Publish Asset
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
