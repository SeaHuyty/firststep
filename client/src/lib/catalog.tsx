"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api } from "./api";
import type { Catalog } from "./types";

const CatalogContext = createContext<Catalog | null>(null);

export const useCatalog = (): Catalog => {
  const c = useContext(CatalogContext);
  if (!c) throw new Error("useCatalog must be used inside <CatalogProvider>");
  return c;
};

// Loads reference data (labels, products, sources) from the server once, before rendering the app.
export function CatalogProvider({ children }: { children: ReactNode }) {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    api.catalog().then(setCatalog, () => setError(true));
  }, []);

  if (error)
    return (
      <div className="p-8 text-sm text-slate-600">
        <p className="font-medium text-slate-900">Can’t reach the server.</p>
        <p className="mt-1">
          Start it with <code className="rounded bg-slate-100 px-1">npm run dev:server</code> and refresh.
        </p>
      </div>
    );
  if (!catalog) return <div className="p-8 text-sm text-slate-500">Loading…</div>;
  return <CatalogContext.Provider value={catalog}>{children}</CatalogContext.Provider>;
}
