"use client";

import { useEffect, useState } from "react";
import { api } from "./api";
import type { Holding, Pct, Profile } from "./types";

// Dollars per fund, worked out by the server: the same split the what-if tests, so every section agrees.
export function useHoldings(profile: Profile, pct: Pct, picks: string[]): Holding[] | null {
  const [state, setState] = useState<{ key: string; data: Holding[] } | null>(null);
  const key = JSON.stringify([profile, pct, picks]);
  useEffect(() => {
    const ctrl = new AbortController();
    api.holdings({ profile, pct, picks }, ctrl.signal).then(
      (data) => setState({ key, data }),
      () => {},
    );
    return () => ctrl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return state && state.key === key ? state.data : null;
}
