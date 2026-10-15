"use client";

import { useEffect, useImperativeHandle, useRef, useState, type Ref } from "react";
import { api } from "@/lib/api";
import { useCatalog } from "@/lib/catalog";
import {
  BUCKETS,
  BUCKET_COLORS,
  usd,
  type Action,
  type Catalog,
  type Pct,
  type ProductGroup,
  type Profile,
} from "@/lib/types";

type Status = "pending" | "applied" | "dismissed" | "stale";
type Proposal = { action: Extract<Action, { type: "allocation" | "products" }>; status: Status };
type Msg = { role: "user" | "assistant"; content: string; notes?: string[]; proposals?: Proposal[] };

const GREETING: Msg = {
  role: "assistant",
  content:
    "Hi, I’m your AI advisor. Tell me about your money and goals, or ask me to change your plan, like “make it safer” or “pick cheap worldwide ETFs”. I’ll show changes on the page.",
};
const SUGGESTIONS = ["I have $10,000 to invest for a house in 3 years", "Make my plan safer", "Pick cheap worldwide ETFs"];

const FIELD_NAMES: Record<string, string> = {
  amount: "Money",
  goal: "Goal",
  horizon: "Horizon",
  emergency: "Emergency savings",
  risk: "Risk",
  debt: "Debt",
};

const profileNote = (u: Partial<Profile>, catalog: Catalog) =>
  "Updated: " +
  Object.entries(u)
    .map(([k, v]) => {
      const labels = catalog.labels[k as keyof Catalog["labels"]];
      return `${FIELD_NAMES[k]} → ${k === "amount" ? usd(v as number) : (labels?.[String(v)] ?? v)}`;
    })
    .join(", ");

export type AdvisorHandle = { ask: (text: string) => void };

export function Advisor({
  ref,
  open,
  onClose,
  profile,
  confirmed,
  pct,
  picks,
  onProfile,
  onApplyAllocation,
  onApplyProducts,
  onGoto,
}: {
  ref: Ref<AdvisorHandle>;
  open: boolean;
  onClose: () => void;
  profile: Profile;
  confirmed: string[];
  pct: Pct | null;
  picks: string[];
  onProfile: (u: Partial<Profile>) => void;
  onApplyAllocation: (after: Pct, reason: string) => Promise<boolean>;
  onApplyProducts: (group: ProductGroup, tickers: string[], reason: string) => boolean;
  onGoto: (step: number) => void;
}) {
  const catalog = useCatalog();
  const [messages, setMessages] = useState<Msg[]>([GREETING]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages, busy, open]);

  async function send(text: string) {
    text = text.trim();
    if (!text || busy) return;
    const history: Msg[] = [...messages, { role: "user", content: text }];
    setMessages(history);
    setInput("");
    setBusy(true);
    setError("");
    try {
      const data = await api.chat({
        messages: history.slice(-20).map(({ role, content }) => ({ role, content })),
        profile,
        confirmed,
        pct,
        picks,
      });

      const notes: string[] = [];
      const proposals: Proposal[] = [];
      for (const a of data.actions ?? []) {
        if (a.type === "profile") {
          onProfile(a.updates);
          notes.push(profileNote(a.updates, catalog));
        } else if (a.type === "goto") onGoto(a.step);
        else proposals.push({ action: a, status: "pending" });
      }
      setMessages([...history, { role: "assistant", content: data.reply, notes, proposals }]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  // Lets the page put a question to the advisor (e.g. "Why this allocation?").
  useImperativeHandle(ref, () => ({ ask: send }));

  function resolve(msgIndex: number, propIndex: number, status: Status) {
    setMessages((ms) =>
      ms.map((m, i) =>
        i !== msgIndex ? m : { ...m, proposals: m.proposals!.map((p, j) => (j === propIndex ? { ...p, status } : p)) },
      ),
    );
  }

  async function apply(msgIndex: number, propIndex: number, p: Proposal) {
    const a = p.action;
    const ok =
      a.type === "allocation" ? await onApplyAllocation(a.after, a.reason) : onApplyProducts(a.group, a.tickers, a.reason);
    resolve(msgIndex, propIndex, ok ? "applied" : "stale");
  }

  return (
    <aside
      className={`fixed inset-y-0 right-0 z-20 flex w-full max-w-sm flex-col border-l border-slate-200 bg-white shadow-xl ${open ? "" : "hidden"}`}
      aria-label="AI advisor"
    >
      <header className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
        <div>
          <p className="text-sm font-semibold text-slate-900">AI advisor</p>
          <p className="text-xs text-slate-500">Proposes changes. You decide.</p>
        </div>
        <button onClick={onClose} className="rounded-md px-2 py-1 text-sm text-slate-500 hover:bg-slate-100" aria-label="Close advisor">
          ✕
        </button>
      </header>

      <div className="flex-1 space-y-3 overflow-y-auto p-4" aria-live="polite">
        {messages.map((m, mi) => (
          <div key={mi} className={m.role === "user" ? "flex justify-end" : "space-y-2"}>
            <p
              className={`max-w-[90%] rounded-2xl px-3.5 py-2 text-sm leading-relaxed ${
                m.role === "user" ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-800"
              }`}
            >
              {m.content}
            </p>
            {m.notes?.map((n) => (
              <p key={n} className="text-xs text-emerald-700">
                ✓ {n}
              </p>
            ))}
            {m.proposals?.map((p, pi) => (
              <ProposalCard key={pi} p={p} onApply={() => apply(mi, pi, p)} onDismiss={() => resolve(mi, pi, "dismissed")} />
            ))}
          </div>
        ))}
        {messages.length === 1 && (
          <div className="flex flex-wrap gap-2">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                onClick={() => send(s)}
                className="rounded-full border border-slate-300 px-3 py-1 text-xs text-slate-600 hover:bg-slate-50"
              >
                {s}
              </button>
            ))}
          </div>
        )}
        {busy && <p className="text-xs text-slate-400">Thinking…</p>}
        {error && <p className="text-xs text-rose-600">{error}</p>}
        <div ref={endRef} />
      </div>

      <form
        className="flex gap-2 border-t border-slate-200 p-3"
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
      >
        <input
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
          placeholder="Message the advisor…"
          value={input}
          maxLength={500}
          onChange={(e) => setInput(e.target.value)}
        />
        <button
          disabled={busy || !input.trim()}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-40"
        >
          Send
        </button>
      </form>
    </aside>
  );
}

function ProposalCard({ p, onApply, onDismiss }: { p: Proposal; onApply: () => void; onDismiss: () => void }) {
  const { buckets, products } = useCatalog();
  const a = p.action;
  return (
    <div className="rounded-xl border border-slate-200 p-3 text-sm">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
        {a.type === "allocation" ? "Proposed allocation" : `Proposed picks: ${a.group}`}
      </p>
      {a.type === "allocation" ? (
        <ul className="mt-2 space-y-1">
          {BUCKETS.filter((b) => a.before[b] !== a.after[b]).map((b) => (
              <li key={b} className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-sm" style={{ background: BUCKET_COLORS[b] }} />
                <span className="flex-1 text-slate-700">{buckets[b].label}</span>
                <span className="text-slate-500">
                  {a.before[b]}% → <strong className="text-slate-900">{a.after[b]}%</strong>
                </span>
              </li>
            ))}
        </ul>
      ) : (
        <ul className="mt-2 space-y-1">
          {a.tickers.map((t) => {
            const prod = products[a.group].find((x) => x.ticker === t);
            return (
              <li key={t} className="text-slate-700">
                <strong className="text-slate-900">{t}</strong> {prod?.name} <span className="text-slate-500">· fee {prod?.fee}</span>
              </li>
            );
          })}
        </ul>
      )}
      <p className="mt-2 text-xs text-slate-500">{a.reason}</p>
      {a.type === "allocation" && a.notes.map((n) => (
        <p key={n} className="mt-1 text-xs text-amber-700">{n}</p>
      ))}
      <div className="mt-3 flex items-center gap-2">
        {p.status === "pending" ? (
          <>
            <button onClick={onApply} className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700">
              Apply
            </button>
            <button onClick={onDismiss} className="rounded-md px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-100">
              Dismiss
            </button>
          </>
        ) : (
          <span className="text-xs text-slate-500">
            {p.status === "applied" ? "✓ Applied" : p.status === "dismissed" ? "Dismissed" : "No longer valid for your current profile"}
          </span>
        )}
      </div>
    </div>
  );
}
