"use client";

// The plan builds up here as Sprout works (docs/standards/onboarding-ux.md section 2): the latest
// card of each kind, in the order of the journey.
import { Gauge, PieChart, ShieldCheck, Target, Wallet } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { prefersReducedMotion } from "@/lib/motion";
import { Button } from "@/components/ui/button";
import { Card as Box, Notice, Skeleton } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { month } from "@/lib/format";
import type { AuditView, Card, Stage } from "@/lib/types";
import {
  AllocationView,
  ComparisonView,
  GoalView,
  PortfolioView,
  ProductsView,
  ProjectionView,
  ReadinessView,
  ReceiptView,
  RiskBadgeView,
  SavingsPlanView,
} from "./cards";

export const PLAN_TYPES = new Set<string>([
  "portfolio", "receipt", "savings_plan", "readiness", "risk_badge", "goal", "allocation",
  "projection", "comparison", "products",
]);

const ORDER = [
  "portfolio",
  "receipt",
  "readiness",
  "savings_plan",
  "risk_badge",
  "goal",
  "allocation",
  "projection",
  "comparison",
  "products",
] as const;

function signature(card: Card): string {
  const text = JSON.stringify(card);
  let h = 0;
  for (let i = 0; i < text.length; i++) h = (h * 31 + text.charCodeAt(i)) | 0;
  return h.toString(36);
}

function latestByType(cards: Card[]): Partial<Record<Card["type"], Card>> {
  const out: Partial<Record<Card["type"], Card>> = {};
  for (const c of cards) out[c.type] = c;
  return out;
}

export function View({ card }: { card: Card }) {
  switch (card.type) {
    case "readiness": return <ReadinessView card={card} />;
    case "savings_plan": return <SavingsPlanView card={card} />;
    case "risk_badge": return <RiskBadgeView card={card} />;
    case "goal": return <GoalView card={card} />;
    case "allocation": return <AllocationView card={card} />;
    case "projection": return <ProjectionView card={card} />;
    case "comparison": return <ComparisonView card={card} />;
    case "receipt": return <ReceiptView card={card} />;
    case "portfolio": return <PortfolioView card={card} />;
    case "products": return <ProductsView card={card} />;
    default: return null;
  }
}

/**
 * A one-second spotlight on the card that just changed (37signals' "yellow fade"; the
 * "One-Second Spotlight" pattern): scroll it into view in the plan pane, then a brief ring that
 * fades, so the change is seen without a lasting distraction.
 */
function useSpotlight(root: React.RefObject<HTMLDivElement | null>, spotlight: { type: string; n: number } | null) {
  useEffect(() => {
    if (!spotlight) return;
    const el = root.current?.querySelector<HTMLElement>(`[data-plan-type="${spotlight.type}"]`);
    if (!el || el.offsetParent === null) return; // hidden (e.g. the plan tab on a phone)
    const reduced = prefersReducedMotion();
    el.scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "start" });
    if (reduced) return;
    const color = getComputedStyle(document.documentElement).getPropertyValue("--fs-primary").trim();
    el.animate(
      [
        { boxShadow: `0 0 0 3px ${color}` },
        { boxShadow: `0 0 0 3px ${color}`, offset: 0.35 },
        { boxShadow: "0 0 0 3px transparent" },
      ],
      { duration: 1600, easing: "ease-out" },
    );
  }, [root, spotlight]);
}

export function PlanPanel({
  cards,
  stage,
  spotlight = null,
}: {
  cards: Card[];
  stage: Stage;
  spotlight?: { type: string; n: number } | null;
}) {
  const root = useRef<HTMLDivElement>(null);
  useSpotlight(root, spotlight);
  const latest = latestByType(cards);
  // Once there is a portfolio, the readiness check and old receipts are history: keep the plan
  // panel about now (progressive disclosure).
  const hide = new Set<string>(stage === "MONITOR" ? ["receipt", "readiness", "goal", "risk_badge", "projection", "products", "comparison"] : stage === "EXECUTED" ? ["readiness"] : []);
  const shown = ORDER.filter((t) => latest[t] && !hide.has(t));
  const coming = upcoming(latest, stage);
  return (
    <div ref={root} className="space-y-4">
      {shown.map((t) => {
        const c = latest[t];
        // Keyed by content, so a card rises in when it first appears and again when it changes
        // (a new plan, a new month), drawing the eye to what Sprout just did.
        return c ? (
          <div key={`${t}:${signature(c)}`} data-plan-type={t} className="animate-rise scroll-mt-2 rounded-md">
            <View card={c} />
          </div>
        ) : null;
      })}
      {coming.length > 0 && <ComingUp items={coming} first={shown.length === 0} />}
    </div>
  );
}

// What the plan will hold, shown as outlines before it exists: an empty state that says what
// will appear and how it fills (NN/g, empty states), and progress you can see (endowed progress).
const MILESTONES = [
  { type: "readiness", icon: Wallet, title: "Money check", text: "Is now a good time? Savings and debts come first." },
  { type: "risk_badge", icon: Gauge, title: "Your risk level", text: "How much up and down suits you." },
  { type: "goal", icon: Target, title: "Your goal", text: "What you're investing for, and by when." },
  { type: "projection", icon: PieChart, title: "Your plan", text: "Your funds, and a range of what could happen." },
] as const;

function upcoming(latest: Partial<Record<Card["type"], Card>>, stage: Stage) {
  // A "not yet" turns the journey into a savings plan; nothing else is coming for now.
  if (latest.savings_plan || stage === "SAVINGS_PLAN" || stage === "EXECUTED" || stage === "MONITOR") return [];
  return MILESTONES.filter((m) => !latest[m.type]);
}

function ComingUp({ items, first }: { items: readonly (typeof MILESTONES)[number][]; first: boolean }) {
  return (
    <section aria-labelledby="coming-up">
      <h3 id="coming-up" className="text-overline uppercase text-muted">
        {first ? "Your plan builds here as you answer" : "Coming up"}
      </h3>
      {/* Dashed and unfilled: a placeholder, clearly not something to click. */}
      <ol className="mt-3 space-y-2">
        {items.map((m, i) => {
          const Icon = m.icon;
          const next = i === 0;
          return (
            <li
              key={m.type}
              className={`flex items-center gap-3 rounded-md border border-dashed px-4 py-3 ${next ? "border-primary" : "border-line"}`}
            >
              <Icon aria-hidden className={`size-5 shrink-0 ${next ? "text-primary" : "text-muted"}`} />
              <p className="min-w-0 flex-1">
                <span className={`block text-label ${next ? "text-ink" : "text-ink-2"}`}>{m.title}</span>
                <span className="block text-body-sm text-muted">{m.text}</span>
              </p>
              {next && <span className="shrink-0 text-caption text-primary">Next</span>}
            </li>
          );
        })}
      </ol>
    </section>
  );
}

export function WatchControls({
  simMonth,
  busy,
  driftAlert,
  onAdvance,
  onRebalance,
}: {
  simMonth: string;
  busy: boolean;
  driftAlert: boolean;
  onAdvance: (args: { months?: number; until?: string }) => void;
  onRebalance: () => void;
}) {
  return (
    <Box overline={`Simulated month: ${month(simMonth)}`} title="Watch your plan over time">
      <p className="text-body-sm text-ink-2">
        Fast-forward through real market history. Looking yearly, not daily, keeps short drops in
        proportion.
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button variant="primary" busy={busy} busyLabel="Moving time…" onClick={() => onAdvance({ months: 12 })}>
          Fast-forward a year
        </Button>
        <Button variant="secondary" disabled={busy} onClick={() => onAdvance({ months: 1 })}>
          A month
        </Button>
        {simMonth < "2020-03" && (
          <Button variant="secondary" disabled={busy} onClick={() => onAdvance({ until: "2020-03" })}>
            Jump to March 2020
          </Button>
        )}
        {driftAlert && (
          <Button variant="ghost" disabled={busy} onClick={onRebalance}>
            Show me a rebalance
          </Button>
        )}
      </div>
    </Box>
  );
}

export function AuditPanel({ sessionId, refreshKey }: { sessionId: string; refreshKey: number }) {
  const [audit, setAudit] = useState<AuditView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let live = true;
    api.audit(sessionId).then(
      (a) => {
        if (!live) return;
        setAudit(a);
        setError(null);
      },
      (e: Error) => live && setError(e.message),
    );
    return () => {
      live = false;
    };
  }, [sessionId, refreshKey, tick]);
  if (error) {
    return <Notice tone="error" title="Couldn't load the audit log" action={<Button onClick={() => setTick(tick + 1)}>Try again</Button>}>{error}</Notice>;
  }
  if (!audit) return <Skeleton className="h-48 w-full" />;
  const events = [...audit.events].reverse();
  return (
    <Box overline="Audit log" title="Every step, chained and checked">
      <Notice tone={audit.check.ok ? "success" : "error"} title={audit.check.ok ? "Chain verified" : "Chain broken"}>
        {audit.check.ok
          ? `${audit.check.events} events. Each one stores the fingerprint of the one before, and the latest matches the copy kept outside the log.`
          : `Problem at event ${audit.check.first_bad_seq ?? "?"}: ${audit.check.reason ?? ""}`}
      </Notice>
      <ol className="mt-3 max-h-[480px] space-y-1 overflow-y-auto font-mono text-caption">
        {events.map((e) => {
          const p = e.payload as Record<string, unknown>;
          const blocked = e.type === "policy" && p.allowed === false;
          return (
            <li key={String(e.seq)} className={`flex gap-2 rounded-sm px-2 py-1 ${blocked ? "bg-danger-soft" : "odd:bg-sunken"}`}>
              <span className="w-8 shrink-0 text-right text-muted">{String(e.seq)}</span>
              <span className="w-20 shrink-0">{String(e.type)}</span>
              <span className="min-w-0 truncate text-ink-2">
                {String(p.tool ?? p.event ?? p.action ?? (typeof p.text === "string" ? p.text.slice(0, 60) : ""))}
                {typeof p.rule_id === "string" && ` · ${p.rule_id}`}
                {blocked && " · blocked"}
              </span>
            </li>
          );
        })}
      </ol>
      <p className="mt-2 flex items-center gap-2 break-all text-caption text-muted">
        <ShieldCheck aria-hidden className="size-4 shrink-0" /> Latest {audit.check.head.slice(0, 24)}…
      </p>
    </Box>
  );
}
