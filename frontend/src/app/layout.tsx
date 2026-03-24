import type { Metadata } from "next";
import "./globals.css";
import Navbar from "@/components/Navbar";
import Sidebar from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "CopolPred - Copolymerisation Reactivity Ratio Prediction",
  description:
    "Plug-and-play ML platform for predicting r₁ and r₂ reactivity ratios from monomer SMILES pairs. 22+ models including Siamese, VAE, LSTM, GAT, Random Forest, XGBoost and more.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen">
        <div className="flex h-screen overflow-hidden">
          <Sidebar />
          <div className="flex flex-1 flex-col overflow-hidden">
            <Navbar />
            <main className="flex-1 overflow-y-auto p-6 flex flex-col">
              <div className="flex-1">
                {children}
              </div>
              <footer className="mt-12 border-t border-[var(--border)] pt-8 pb-12 text-center text-sm font-medium tracking-wide text-[var(--text-muted)] w-full">
                created and managed by S. Mohanty
              </footer>
            </main>
          </div>
        </div>
      </body>
    </html>
  );
}
