// The one fetch wrapper: same-origin /api (next.config.ts proxies it to FastAPI), a timeout on
// every request, and errors a person can read. docs/standards/frontend.md section 4.
import type { AuditView, SessionView, TurnOut } from "./types";

const TIMEOUT_MS = 15_000;
const TURN_TIMEOUT_MS = 60_000; // an LLM turn can take a while

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, body?: unknown, timeoutMs = TIMEOUT_MS): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`/api${path}`, {
      method: body === undefined ? "GET" : "POST",
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });
    const data: unknown = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail =
        typeof data === "object" && data !== null
          ? ((data as { error?: string; detail?: string }).error ??
            (data as { detail?: string }).detail)
          : undefined;
      throw new ApiError(
        typeof detail === "string" ? detail : `Something went wrong (${res.status}).`,
        res.status,
      );
    }
    return data as T;
  } catch (e) {
    if (e instanceof ApiError) throw e;
    if (e instanceof DOMException && e.name === "AbortError") {
      throw new ApiError("Sprout didn't answer in time. Your answers are saved. Try again.", 0);
    }
    throw new ApiError("Can't reach FirstStep. Check your connection and try again.", 0);
  } finally {
    clearTimeout(timer);
  }
}

/** A chip or button. `label` is the words on it, kept as the person's message in the chat. */
export type Action = { tool: string; args?: Record<string, unknown>; label?: string };

export const api = {
  newSession: (persona?: string) => request<SessionView>("/sessions", { persona: persona ?? null }),
  session: (id: string) => request<SessionView>(`/sessions/${encodeURIComponent(id)}`),
  say: (id: string, text: string) =>
    request<TurnOut>(`/sessions/${encodeURIComponent(id)}/turn`, { text }, TURN_TIMEOUT_MS),
  act: (id: string, action: Action) =>
    request<TurnOut>(
      `/sessions/${encodeURIComponent(id)}/turn`,
      { action: { tool: action.tool, args: action.args ?? {}, label: action.label } },
      TURN_TIMEOUT_MS,
    ),
  confirm: (id: string, proposalId: string) =>
    request<TurnOut>(
      `/sessions/${encodeURIComponent(id)}/confirm/${encodeURIComponent(proposalId)}`,
      {},
      TURN_TIMEOUT_MS,
    ),
  audit: (id: string) => request<AuditView>(`/sessions/${encodeURIComponent(id)}/audit`),
};
