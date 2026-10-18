"use client";

// The plan's cards by type, the time controls and the audit log, used by the dashboard and chat.
import { ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card as Box, Notice, Skeleton } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { month } from "@/lib/format";
import type { AuditView, Card } from "@/lib/types";
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
    // Moving time is the next step here, so it sits under the chat, where the person is looking.
    <div className="rounded-md border border-line bg-surface p-3">
      <p className="text-body-sm text-ink-2">
        <span className="text-label text-ink">Simulated month: {month(simMonth)}</span>. Move through real
        market history; looking yearly, not daily, keeps short drops in proportion.
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
    </div>
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
