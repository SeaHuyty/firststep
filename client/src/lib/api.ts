import type { Action, Catalog, Market, Pct, PlanResult, Profile } from "./types";

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
  plan: (profile: Profile, signal?: AbortSignal) => request<PlanResult>("/plan", { profile }, signal),
  validateAllocation: (profile: Profile, pct: Pct) =>
    request<{ valid: boolean }>("/allocation/validate", { profile, pct }).then((r) => r.valid),
  projection: (p: { amount: number; monthly: number; years: number; risk: number }, signal?: AbortSignal) =>
    request<{ series: [number[], number[], number[]] }>("/projection", p, signal).then((r) => r.series),
  chat: (body: {
    messages: { role: "user" | "assistant"; content: string }[];
    profile: Profile;
    confirmed: string[];
    pct: Pct | null;
    picks: string[];
  }) => request<{ reply: string; actions: Action[] }>("/chat", body),
};

// Streams the explanation text; calls onText with the text accumulated so far.
export async function streamExplanation(
  body: { profile: Profile; pct: Pct },
  onText: (text: string) => void,
  signal: AbortSignal,
): Promise<string> {
  const res = await fetch("/api/explain", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) throw new Error(String(res.status));
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let acc = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    acc += decoder.decode(value, { stream: true });
    onText(acc);
  }
  return acc;
}
