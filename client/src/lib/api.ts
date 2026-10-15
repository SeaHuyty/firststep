import type { Action, Catalog, Market, Pct, PlanResult, Profile, Stocks, WhatIf } from "./types";

// Same-origin: next.config.ts proxies /api/* to the FastAPI server.
async function request<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error ?? data.detail ?? `Request failed (${res.status})`);
  return data as T;
}

export const api = {
  catalog: () => request<Catalog>("/catalog"),
  market: () => request<Market>("/market"),
  stocks: (risk: number, signal?: AbortSignal) => request<Stocks>(`/stocks?risk=${risk}`, undefined, signal),
  plan: (profile: Profile, signal?: AbortSignal) => request<PlanResult>("/plan", { profile }, signal),
  validateAllocation: (profile: Profile, pct: Pct) =>
    request<{ valid: boolean }>("/allocation/validate", { profile, pct }).then((r) => r.valid),
  whatIf: (
    body: {
      profile: Profile;
      pct: Pct | null;
      picks: string[];
      monthly: number;
      years: number;
      risk: number;
      basis: "history" | "assumed";
    },
    signal?: AbortSignal,
  ) => request<WhatIf>("/whatif", body, signal),
  chat: (body: {
    messages: { role: "user" | "assistant"; content: string }[];
    profile: Profile;
    confirmed: string[];
    pct: Pct | null;
    picks: string[];
  }) => request<{ reply: string; actions: Action[] }>("/chat", body),
};
