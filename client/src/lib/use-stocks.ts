"use client";

import { useEffect, useState } from "react";
import { api } from "./api";
import type { Stocks } from "./types";

// Stocks the server screened from the S&P 500 for this risk level. The first load takes about a minute, so
// ask again until it is ready.
export function useStocks(risk: number): Stocks | null {
  const [state, setState] = useState<{ risk: number; data: Stocks } | null>(null);
  useEffect(() => {
    const ctrl = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    const load = () =>
      api.stocks(risk, ctrl.signal).then(
        (data) => {
          setState({ risk, data });
          if (!data.ready) timer = setTimeout(load, 6000);
        },
        () => {
          if (!ctrl.signal.aborted) timer = setTimeout(load, 10000);
        },
      );
    load();
    return () => {
      clearTimeout(timer);
      ctrl.abort();
    };
  }, [risk]);
  return state && state.risk === risk ? state.data : null;
}
