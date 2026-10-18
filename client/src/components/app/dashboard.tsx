"use client";

// After the questions: a dashboard with a sidebar, the shape of Betterment, Wealthfront and most
// banking apps, and of the team's sketch. Home says where you stand and the one next step; Plan
// shows what the money is made of; Funds is the library to browse, compare and swap. Every
// action still goes through the same tools and the guardian as before.
import { ArrowRight, Home, Library, PieChart, ScrollText } from "lucide-react";
import { type ReactNode, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card as Box, Notice, RiskBadge } from "@/components/ui/primitives";
import { FAMILY_LABEL } from "@/lib/copy";
import { duration, money, month } from "@/lib/format";
import type { Card, CardOf, Stage } from "@/lib/types";
import { Avatar } from "@/components/sprout/bubble";
import {
  AllocationView,
  ComparisonView,
  PortfolioView,
  ProjectionView,
  ReadinessView,
  ReceiptView,
  SavingsPlanView,
} from "@/components/sprout/cards";
import { AllocationDonut, FamilyDot } from "@/components/sprout/charts";
import { AuditPanel, WatchControls } from "@/components/sprout/plan-panel";
import { Safeguards } from "@/components/sprout/safeguards";

export type View = "home" | "plan" | "funds" | "activity";

export type Product = {
  id: string;
  name: string;
  asset_class: string;
  family: string;
  risk_rating: string;
  ter_pct: number;
  liquidity_days: number;
  description: string;
};

export type Latest = Partial<{ [K in Card["type"]]: CardOf<K> }>;

export function latestByType(cards: Card[]): Latest {
  const out: Record<string, Card> = {};
  for (const c of cards) out[c.type] = c;
  return out as Latest;
}

const NAV: { view: View; label: string; icon: typeof Home }[] = [
  { view: "home", label: "Home", icon: Home },
  { view: "plan", label: "Plan", icon: PieChart },
  { view: "funds", label: "Funds", icon: Library },
  { view: "activity", label: "Activity", icon: ScrollText },
];

/** A sidebar on desktop, a bottom tab bar on phones (the thumb zone). */
export function Nav({ view, onView }: { view: View; onView: (v: View) => void }) {
  return (
    <nav aria-label="Sections" className="fixed inset-x-0 bottom-0 z-20 border-t border-line bg-surface lg:static lg:w-52 lg:shrink-0 lg:border-0 lg:bg-transparent">
      <ul className="flex lg:sticky lg:top-6 lg:flex-col lg:gap-1">
        {NAV.map(({ view: v, label, icon: Icon }) => {
          const on = v === view;
          return (
            <li key={v} className="flex-1 lg:flex-none">
              <button
                type="button"
                aria-current={on ? "page" : undefined}
                onClick={() => onView(v)}
                className={`flex min-h-14 w-full flex-col items-center justify-center gap-1 text-caption lg:min-h-11 lg:flex-row lg:justify-start lg:gap-3 lg:rounded-md lg:px-3 lg:text-label ${on ? "text-primary lg:bg-primary-soft" : "text-ink-2 hover:text-ink lg:hover:bg-sunken"}`}
              >
                <Icon aria-hidden className="size-5" />
                {label}
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

/** Sprout's latest word and any rule it hit, at the top of the page, where the person looks. */
export function LatestNote({
  reply,
  notices,
  onOpenChat,
}: {
  reply: string;
  notices: Card[];
  onOpenChat: () => void;
}) {
  if (!reply && notices.length === 0) return null;
  // A notice drops a sentence Sprout's note above already says.
  const squash = (t: string) => t.replace(/\s+/g, " ").trim().toLowerCase();
  const body = (t: string) => (reply && squash(reply).includes(squash(t)) ? null : t);
  return (
    <div className="mb-6 space-y-3">
      {reply && (
        <div className="flex items-start gap-3 rounded-md border border-line bg-surface p-3">
          <Avatar />
          <p className="flex-1 text-body text-ink-2">{reply}</p>
          <button type="button" onClick={onOpenChat} className="min-h-11 shrink-0 rounded-sm px-2 text-label text-primary hover:bg-primary-soft">
            Reply
          </button>
        </div>
      )}
      {notices.map((c, i) =>
        c.type === "refusal" ? (
          <Notice key={i} tone="error" title={c.title} ruleId={c.rule_id}>{[body(c.text), c.next_step].filter(Boolean).join(" ") || null}</Notice>
        ) : c.type === "pause" ? (
          <Notice key={i} tone="pause" title={c.title} ruleId={c.rule_id}>{body(c.text)}</Notice>
        ) : c.type === "alert" ? (
          <Notice key={i} tone={c.tone === "pause" ? "pause" : "info"} title={c.title} ruleId={c.rule_id}>{body(c.text)}</Notice>
        ) : null,
      )}
    </div>
  );
}

function PageTitle({ overline, title, children }: { overline: string; title: string; children?: ReactNode }) {
  return (
    <header className="mb-6">
      <p className="text-overline uppercase text-muted">{overline}</p>
      <h1 className="mt-1 font-display text-display-2 text-ink">{title}</h1>
      {children}
    </header>
  );
}

function Pill({ children }: { children: ReactNode }) {
  return <span className="inline-flex min-h-9 items-center gap-2 rounded-full border border-line bg-surface px-3 text-label text-ink">{children}</span>;
}

/** The next step, always the one primary button on the page. */
function NextStep({ stage, latest, busy, onPrepare, onReview }: {
  stage: Stage;
  latest: Latest;
  busy: boolean;
  onPrepare: () => void;
  onReview: (c: CardOf<"confirm">) => void;
}) {
  const confirm = latest.confirm;
  if (stage === "CONFIRM" && confirm) {
    return (
      <Button variant="primary" onClick={() => onReview(confirm)} icon={<ArrowRight aria-hidden className="size-5" />}>
        Review {confirm.orders.length} orders
      </Button>
    );
  }
  if (stage === "PROPOSE" && latest.projection) {
    return (
      <Button variant="primary" busy={busy} busyLabel="Preparing…" onClick={onPrepare} icon={<ArrowRight aria-hidden className="size-5" />}>
        Review the orders
      </Button>
    );
  }
  return null;
}

/** What the money is made of: the donut with the words as its legend. */
function MixCard({ card, onOpenPlan }: { card: CardOf<"allocation">; onOpenPlan: () => void }) {
  const parts = Object.entries(card.families).filter(([, w]) => w > 0);
  return (
    <Box overline="What your money is made of" title={money(card.total_usd)}>
      <AllocationDonut families={card.families} total={card.total_usd}>
        <ul className="w-full space-y-2">
          {parts.map(([family, weight]) => (
            <li key={family} className="flex items-center gap-2 text-body text-ink-2">
              <FamilyDot family={family} />
              <span className="flex-1">{family === "cash" ? "Deposits & cash" : FAMILY_LABEL[family]}</span>
              <span className="tnum text-label text-ink">{Math.round(weight)}%</span>
            </li>
          ))}
        </ul>
      </AllocationDonut>
      <button type="button" onClick={onOpenPlan} className="mt-3 inline-flex min-h-11 items-center gap-1 text-label text-primary">
        See the plan <ArrowRight aria-hidden className="size-4" />
      </button>
    </Box>
  );
}

/** Three cases in the person's money, the short form of "What could happen". */
function OutcomesCard({ card, onOpenPlan }: { card: CardOf<"projection">; onOpenPlan: () => void }) {
  const end = card.years.length - 1;
  const rows = [
    ["In a bad case", card.p10[end] ?? 0],
    ["Most likely", card.p50[end] ?? 0],
    ["In a good case", card.p90[end] ?? 0],
  ] as const;
  return (
    <Box overline="What could happen" title={`In ${card.years[end]} years`}>
      <p className="text-body-sm text-ink-2">You would put in {money(card.paid_in[end] ?? 0)} in total.</p>
      <dl className="mt-3 divide-y divide-line">
        {rows.map(([label, value]) => (
          <div key={label} className={`flex items-baseline justify-between py-2 ${label === "Most likely" ? "font-semibold" : ""}`}>
            <dt className="text-body text-ink-2">{label}</dt>
            <dd className="tnum text-num-card text-ink">{money(value)}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-2 text-body-sm text-ink-2">
        {Math.round(card.prob_below_paid_in_year1 * 100)} out of 100 replays ended year one below what was put in.
      </p>
      <button type="button" onClick={onOpenPlan} className="mt-2 inline-flex min-h-11 items-center gap-1 text-label text-primary">
        See the full range <ArrowRight aria-hidden className="size-4" />
      </button>
    </Box>
  );
}

export function HomeView(props: {
  stage: Stage;
  latest: Latest;
  allCards: Card[];
  simMonth: string;
  busy: boolean;
  driftAlert: boolean;
  onView: (v: View) => void;
  onPrepare: () => void;
  onReview: (c: CardOf<"confirm">) => void;
  onAdvance: (args: { months?: number; until?: string }) => void;
  onRebalance: () => void;
}) {
  const { stage, latest, allCards, busy, onView } = props;
  if (stage === "SAVINGS_PLAN") {
    return (
      <>
        <PageTitle overline="Home" title="Your plan for now" />
        <div className="space-y-4">
          {latest.readiness && <ReadinessView card={latest.readiness} />}
          {latest.savings_plan && <SavingsPlanView card={latest.savings_plan} />}
          <Safeguards cards={allCards} stage={stage} />
        </div>
      </>
    );
  }
  if (stage === "EXECUTED" || stage === "MONITOR") {
    return (
      <>
        <PageTitle overline="Home" title="Your practice account" />
        <div className="grid gap-4 xl:grid-cols-2">
          <div className="space-y-4">
            {latest.portfolio ? <PortfolioView card={latest.portfolio} /> : latest.receipt && <ReceiptView card={latest.receipt} />}
            <WatchControls simMonth={props.simMonth} busy={busy} driftAlert={props.driftAlert} onAdvance={props.onAdvance} onRebalance={props.onRebalance} />
          </div>
          <div className="space-y-4">
            {latest.allocation && <MixCard card={latest.allocation} onOpenPlan={() => onView("plan")} />}
            <Safeguards cards={allCards} stage={stage} />
          </div>
        </div>
      </>
    );
  }
  const goal = latest.goal;
  return (
    <>
      <PageTitle overline="Home" title="Your investment plan">
        <div className="mt-4 flex flex-wrap gap-2">
          {goal && <Pill>{money(goal.lump_sum_usd)} now · {money(goal.monthly_usd)} a month</Pill>}
          {latest.risk_badge && (
            <Pill>
              <RiskBadge code={latest.risk_badge.client_class} label={latest.risk_badge.label} />
            </Pill>
          )}
          {goal && <Pill>{goal.name}: {money(goal.target_usd)} in {duration(goal.horizon_years * 12)}</Pill>}
        </div>
      </PageTitle>
      <div className="grid gap-4 xl:grid-cols-2">
        {latest.allocation && <MixCard card={latest.allocation} onOpenPlan={() => onView("plan")} />}
        {latest.projection && <OutcomesCard card={latest.projection} onOpenPlan={() => onView("plan")} />}
      </div>
      <div className="mt-6 flex flex-col gap-3 rounded-md border border-line bg-surface p-4 sm:flex-row sm:items-center">
        <p className="flex-1 text-body text-ink-2">
          {stage === "CONFIRM"
            ? "Your orders are ready. Check them, then confirm. Nothing is bought until you do."
            : "Happy with the plan? See exactly what would be bought. Nothing happens until you confirm."}
        </p>
        <NextStep stage={stage} latest={latest} busy={busy} onPrepare={props.onPrepare} onReview={props.onReview} />
      </div>
      <div className="mt-4">
        <Safeguards cards={allCards} stage={stage} />
      </div>
    </>
  );
}

const MEANING: Record<string, string> = {
  cash: "Holds steady, for money you might need soon.",
  bonds: "Loans to governments that pay interest, with small ups and downs.",
  stocks: "Small pieces of thousands of companies; grows most over years, but can drop.",
  gold: "Often moves differently from stocks.",
};

/** One card per kind of investment, each listing its funds (the sketch's columns). */
function FamilyCards({ card, onChange }: { card: CardOf<"allocation">; onChange: (family: string) => void }) {
  const families = Object.entries(card.families).filter(([, w]) => w > 0);
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {families.map(([family, weight]) => {
        const lines = card.lines.filter((l) => l.family === family);
        const amount = lines.reduce((sum, l) => sum + Number(l.amount_usd), 0);
        return (
          <section key={family} className="rounded-md border border-line bg-surface p-4">
            <div className="flex items-center gap-2">
              <FamilyDot family={family} />
              <h3 className="flex-1 text-title text-ink">{family === "cash" ? "Deposits & cash" : FAMILY_LABEL[family]}</h3>
              <span className="tnum text-label text-ink-2">{Math.round(weight)}% · {money(amount)}</span>
            </div>
            <p className="mt-1 text-body-sm text-ink-2">{MEANING[family]}</p>
            <ul className="mt-3 divide-y divide-line">
              {lines.map((l) => (
                <li key={l.product_id} className="flex items-center justify-between gap-3 py-2 text-body">
                  <span className="min-w-0 text-ink">{l.name}</span>
                  <span className="tnum shrink-0 text-ink-2">{money(l.amount_usd)}</span>
                </li>
              ))}
            </ul>
            <button type="button" onClick={() => onChange(family)} className="mt-2 inline-flex min-h-11 items-center gap-1 text-label text-primary">
              Compare or change these funds <ArrowRight aria-hidden className="size-4" />
            </button>
          </section>
        );
      })}
    </div>
  );
}

export function PlanView(props: {
  stage: Stage;
  latest: Latest;
  busy: boolean;
  onFunds: (family: string) => void;
  onPrepare: () => void;
  onReview: (c: CardOf<"confirm">) => void;
}) {
  const { stage, latest } = props;
  if (stage === "SAVINGS_PLAN") {
    return (
      <>
        <PageTitle overline="Plan" title="Get ready to invest" />
        {latest.savings_plan && <SavingsPlanView card={latest.savings_plan} />}
      </>
    );
  }
  const allocation = latest.allocation;
  if (!allocation) return <PageTitle overline="Plan" title="Your plan appears here" />;
  const watching = stage === "EXECUTED" || stage === "MONITOR";
  return (
    <>
      <PageTitle overline="Plan" title={/^C\d/.test(allocation.label) ? `${allocation.label} plan` : "Your plan, with your changes"}>
        <p className="mt-2 text-body text-ink-2">
          {money(allocation.total_usd)} across {allocation.lines.length} low-cost funds, about {money(allocation.fee_usd_a_year)} a year in fees.
        </p>
      </PageTitle>
      <div className="space-y-6">
        {watching && latest.portfolio ? (
          <Box overline={`Practice account · ${month(latest.portfolio.sim_month)}`} title="What you hold now">
            <ul className="divide-y divide-line">
              {latest.portfolio.holdings.map((h) => (
                <li key={h.product_id} className="flex items-center gap-3 py-2 text-body">
                  <FamilyDot family={h.family} />
                  <span className="min-w-0 flex-1 text-ink">{h.name}</span>
                  <span className="tnum text-ink">{money(h.value_usd)}</span>
                  <span className="tnum w-24 text-right text-body-sm text-ink-2">{h.weight_pct}% (aim {h.target_pct}%)</span>
                </li>
              ))}
            </ul>
          </Box>
        ) : (
          <FamilyCards card={allocation} onChange={props.onFunds} />
        )}
        {!watching && latest.comparison && <ComparisonView card={latest.comparison} />}
        {!watching && latest.projection && <ProjectionView card={latest.projection} />}
        {!watching && (
          <details className="rounded-md border border-line bg-surface p-4">
            <summary className="min-h-11 cursor-pointer text-label text-primary">The honest part, fees and every fund</summary>
            <div className="mt-3">
              <AllocationView card={allocation} />
            </div>
          </details>
        )}
        {!watching && (
          <div>
            <NextStep stage={stage} latest={latest} busy={props.busy} onPrepare={props.onPrepare} onReview={props.onReview} />
          </div>
        )}
      </div>
    </>
  );
}

const FILTERS = [
  { key: "all", label: "All" },
  { key: "cash", label: "Deposits & cash" },
  { key: "bonds", label: "Bonds" },
  { key: "stocks", label: "Stocks" },
  { key: "gold", label: "Gold" },
] as const;

/**
 * The fund library: every fund on the shelf, with what it is in words, its cost on $1,000 and its
 * risk. Funds above the person's level are shown, but marked and never offered (SUIT-01).
 * "Swap into plan" replaces the plan's fund of the same kind; the guardian checks the new mix.
 */
export function FundsView({
  stage,
  products,
  latest,
  maxRating,
  busy,
  filter,
  onFilter,
  onCompare,
  onSwap,
}: {
  stage: Stage;
  products: Product[];
  latest: Latest;
  maxRating: string | null;
  busy: boolean;
  filter: string;
  onFilter: (f: string) => void;
  onCompare: (ids: string[], label: string) => void;
  onSwap: (out: string, inn: string, label: string) => void;
}) {
  const [choosing, setChoosing] = useState<string | null>(null);
  const plan = latest.allocation;
  const editable = stage === "PROPOSE" && Boolean(plan);
  const inPlan = new Set(plan?.lines.map((l) => l.product_id) ?? []);
  const shown = products.filter((p) => filter === "all" || p.family === filter);
  const level = (r: string) => Number(r.slice(1));
  return (
    <>
      <PageTitle overline="Funds" title="The fund library">
        <p className="mt-2 text-body text-ink-2">
          Every fund FirstStep offers.{" "}
          {maxRating ? `Your level allows funds rated up to ${maxRating}.` : "Finish the questions to see which fit you."}
        </p>
      </PageTitle>
      <div role="group" aria-label="Filter funds" className="mb-4 flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            type="button"
            aria-pressed={filter === f.key}
            onClick={() => onFilter(f.key)}
            className={`min-h-11 rounded-full border-[1.5px] border-primary px-4 text-label ${filter === f.key ? "bg-primary text-on-primary" : "bg-surface text-primary hover:bg-primary-soft"}`}
          >
            {f.label}
          </button>
        ))}
      </div>
      {latest.comparison && <div className="mb-4"><ComparisonView card={latest.comparison} /></div>}
      <ul className="grid gap-3 md:grid-cols-2">
        {shown.map((p) => {
          const mine = inPlan.has(p.id);
          const above = maxRating !== null && level(p.risk_rating) > level(maxRating);
          const sameKind = plan?.lines.filter((l) => l.family === p.family) ?? [];
          const peers = sameKind.filter((l) => l.product_id !== p.id);
          return (
            <li key={p.id} className={`flex flex-col rounded-md border bg-surface p-4 ${mine ? "border-primary" : "border-line"}`}>
              <div className="flex items-start gap-2">
                <FamilyDot family={p.family} />
                <h3 className="flex-1 text-title text-ink">{p.name}</h3>
                <span className="shrink-0 rounded-full border border-border-strong bg-sunken px-2 font-mono text-mono text-ink-2">{p.risk_rating}</span>
              </div>
              <p className="mt-1 flex-1 text-body-sm text-ink-2">{p.description}</p>
              <p className="mt-2 text-body-sm text-ink-2">
                <span className="tnum text-ink">${(p.ter_pct * 10).toFixed(2)}</span> a year on every $1,000 · money back in {p.liquidity_days} {p.liquidity_days === 1 ? "day" : "days"}
              </p>
              {mine && <p className="mt-2 text-label text-primary">In your plan</p>}
              {above && <p className="mt-2 text-label text-sun-ink">Above your level ({maxRating} at most), so it can&apos;t go in your plan.</p>}
              {editable && !mine && !above && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {peers.length > 0 && (
                    <Button variant="secondary" disabled={busy} onClick={() => onCompare([peers[0]!.product_id, p.id], `Compare ${p.name} with ${peers[0]!.name}`)}>
                      Compare
                    </Button>
                  )}
                  {peers.length === 1 && (
                    <Button variant="ghost" disabled={busy} onClick={() => onSwap(peers[0]!.product_id, p.id, `Swap ${peers[0]!.name} for ${p.name}`)}>
                      Swap into plan
                    </Button>
                  )}
                  {peers.length > 1 && (
                    <Button variant="ghost" disabled={busy} aria-expanded={choosing === p.id} onClick={() => setChoosing(choosing === p.id ? null : p.id)}>
                      Swap into plan
                    </Button>
                  )}
                  {peers.length === 0 && <p className="text-body-sm text-muted">Your plan holds no {FAMILY_LABEL[p.family]?.toLowerCase()}.</p>}
                </div>
              )}
              {choosing === p.id && (
                <div className="mt-3 rounded-sm bg-sunken p-3">
                  <p className="text-label text-ink">Replace which fund?</p>
                  <ul className="mt-2 space-y-1">
                    {peers.map((l) => (
                      <li key={l.product_id}>
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => {
                            setChoosing(null);
                            onSwap(l.product_id, p.id, `Swap ${l.name} for ${p.name}`);
                          }}
                          className="min-h-11 w-full rounded-sm px-2 text-left text-body text-primary hover:bg-primary-soft"
                        >
                          {l.name} ({l.weight_pct}%)
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </li>
          );
        })}
      </ul>
      {!editable && plan && <p className="mt-4 text-body-sm text-muted">Comparing and swapping funds is open while you build your plan, before the orders.</p>}
    </>
  );
}

export function ActivityView({ sessionId, refreshKey }: { sessionId: string; refreshKey: number }) {
  return (
    <>
      <PageTitle overline="Activity" title="Every step, on record">
        <p className="mt-2 text-body text-ink-2">Each event stores the fingerprint of the one before, so any change would show.</p>
      </PageTitle>
      <AuditPanel sessionId={sessionId} refreshKey={refreshKey} />
    </>
  );
}

