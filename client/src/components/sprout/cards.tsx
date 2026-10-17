"use client";

// One view per card type the server sends. Formatting only: no finance happens here.
import { useState } from "react";
import { Card, DataTable, Notice, RiskBadge, RuleChip } from "@/components/ui/primitives";
import { FAMILY_LABEL } from "@/lib/copy";
import { chance, duration, fee, money, moneyCents, moneyChange, month, pctChange } from "@/lib/format";
import type { CardOf } from "@/lib/types";
import { AllocationDonut, ProjectionFan } from "./charts";

type WhyLine = { rule_id?: string | null; text: string };

/** "Why?" opens the rules behind a number: one click, never deeper (progressive disclosure). */
export function Why({ lines, label = "Why?" }: { lines: WhyLine[]; label?: string }) {
  const [open, setOpen] = useState(false);
  if (lines.length === 0) return null;
  return (
    <div>
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className="min-h-11 rounded-sm text-label text-primary underline decoration-dotted underline-offset-4"
      >
        {open ? "Hide why" : label}
      </button>
      {open && (
        <ul className="mt-1 space-y-2 rounded-sm bg-sunken p-3">
          {lines.map((l, i) => (
            <li key={i} className="flex items-start gap-2 text-body-sm text-ink-2">
              {l.rule_id && <RuleChip id={l.rule_id} />}
              <span>{l.text}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function ReadinessView({ card }: { card: CardOf<"readiness"> }) {
  if (card.ready) {
    return (
      <Notice tone="success" title="You're ready to start">
        Your savings cover {card.emergency_months.toFixed(1)} months of costs, and you have no
        expensive debt. About {money(card.investable_monthly_usd)} a month is left over.
      </Notice>
    );
  }
  return (
    <Notice tone="pause" title="Not yet, and here's why">
      <ul className="mt-1 space-y-2">
        {card.reasons.map((r) => (
          <li key={r.rule_id} className="flex items-start gap-2">
            {r.rule_id && <RuleChip id={r.rule_id} />}
            <span>{r.text}</span>
          </li>
        ))}
      </ul>
    </Notice>
  );
}

export function SavingsPlanView({ card }: { card: CardOf<"savings_plan"> }) {
  return (
    <Card overline="Your plan for now" title="Get ready to invest, step by step">
      <ol className="space-y-3">
        {card.steps.map((s, i) => (
          <li key={s.action} className="flex gap-3">
            <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary-soft text-label text-primary">
              {i + 1}
            </span>
            <div>
              <p className="text-title">{s.title}</p>
              <p className="text-body-sm text-ink-2">
                {money(s.monthly_usd)} a month for {duration(s.months)}
                {s.action === "pay_debt" && s.interest_usd > 0 && `; about ${money(s.interest_usd)} of interest on the way`}
                {s.action !== "pay_debt" && `, until you have ${money(s.target_usd)}`}.
              </p>
            </div>
          </li>
        ))}
      </ol>
      {card.ready_month && card.months_to_ready !== null && (
        <p className="mt-4 rounded-sm bg-primary-soft p-3 text-body text-ink">
          You could be ready to invest by <strong>{month(card.ready_month)}</strong>, in{" "}
          {duration(card.months_to_ready)}. I&apos;ll check in then.
        </p>
      )}
    </Card>
  );
}

export function RiskBadgeView({ card }: { card: CardOf<"risk_badge"> }) {
  return (
    <Card overline="Your risk level">
      <div className="flex flex-wrap items-center gap-3">
        <RiskBadge code={card.client_class} label={card.label} />
      </div>
      <p className="mt-2 text-body text-ink-2">{card.summary}</p>
      <dl className="mt-3 grid grid-cols-2 gap-3 text-body-sm">
        <div className="rounded-sm bg-sunken p-3">
          <dt className="text-muted">How much risk you want</dt>
          <dd className="text-num-card tnum">{card.tolerance} of 5</dd>
        </div>
        <div className="rounded-sm bg-sunken p-3">
          <dt className="text-muted">How much loss you could afford</dt>
          <dd className="text-num-card tnum">{card.capacity} of 5</dd>
        </div>
      </dl>
      <div className="mt-2">
        <Why lines={card.why} />
      </div>
    </Card>
  );
}

export function GoalView({ card }: { card: CardOf<"goal"> }) {
  return (
    <Card overline="Your goal" title={card.name}>
      <p className="text-body text-ink-2">
        {money(card.target_usd)} in {card.horizon_years} years: {money(card.lump_sum_usd)} now and{" "}
        {money(card.monthly_usd)} a month.
      </p>
      {card.capped && (
        <p className="mt-2 flex items-start gap-2 text-body-sm text-ink-2">
          <RuleChip id="HOR-01" /> A short goal keeps your plan at {card.client_class} or below.
        </p>
      )}
    </Card>
  );
}

export function AllocationView({ card }: { card: CardOf<"allocation"> }) {
  return (
    <Card overline={`Proposed plan · ${card.client_class}`} title={card.label}>
      <AllocationDonut families={card.families} total={card.total_usd} />
      <ul className="mt-4 divide-y divide-line">
        {card.lines.map((l) => (
          <li key={l.product_id} className="py-3">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-body text-ink">{l.name}</p>
                <p className="text-caption text-muted">
                  {FAMILY_LABEL[l.family]} · <span className="font-mono">{l.risk_rating}</span>
                </p>
              </div>
              <div className="text-right">
                <p className="tnum text-body">{money(l.amount_usd)}</p>
                <p className="tnum text-caption text-muted">{l.weight_pct}%</p>
              </div>
            </div>
            <Why lines={l.why} />
          </li>
        ))}
      </ul>
      <p className="mt-3 text-body-sm text-ink-2">
        Fees: {fee(card.fee_pct)}, about {moneyCents(card.fee_usd_a_year)} a year on{" "}
        {money(card.total_usd)}.
      </p>
    </Card>
  );
}

export function ProjectionView({ card }: { card: CardOf<"projection"> }) {
  const end = card.years.length - 1;
  return (
    <Card overline="What could happen" title="Range of outcomes">
      <p className="mb-3 text-body text-ink-2">
        After {card.years[end]} years: about {money(card.p10[end] ?? 0)} in a bad case,{" "}
        {money(card.p50[end] ?? 0)} typically, {money(card.p90[end] ?? 0)} in a good case. You
        would put in {money(card.paid_in[end] ?? 0)}.
      </p>
      <ProjectionFan years={card.years} p10={card.p10} p50={card.p50} p90={card.p90} paidIn={card.paid_in} />
      <p className="mt-3 text-body-sm text-ink-2">
        Chance of ending the first year below what you put in: {chance(card.prob_below_paid_in_year1)}.
        {card.prob_reach_goal !== null && card.goal_usd !== null &&
          ` Chance of reaching ${money(card.goal_usd)}: ${chance(card.prob_reach_goal)}.`}
      </p>
      <p className="mt-2 text-caption text-muted">{card.caption}</p>
    </Card>
  );
}

export function ComparisonView({ card }: { card: CardOf<"comparison"> }) {
  return (
    <Card overline={`As of ${month(card.as_of)}`} title="Side by side">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[420px] border-collapse text-body-sm">
          <thead>
            <tr className="border-b border-line text-left text-muted">
              <th scope="col" className="py-2 font-medium">Fund</th>
              <th scope="col" className="py-2 text-right font-medium">Fee on $1,000</th>
              <th scope="col" className="py-2 text-right font-medium">5 years, a year</th>
              <th scope="col" className="py-2 text-right font-medium">Worst 12 months</th>
            </tr>
          </thead>
          <tbody>
            {card.rows.map((r) => (
              <tr key={r.id} className="border-b border-line last:border-0">
                <th scope="row" className="py-2 text-left font-normal">
                  {r.name} <span className="font-mono text-caption text-muted">{r.risk_rating}</span>
                </th>
                <td className="tnum py-2 text-right">{moneyCents(r.fee_per_year_on_1000_usd)} a year</td>
                <td className="tnum py-2 text-right">{r.return_5y_pct_a_year === null ? "–" : pctChange(r.return_5y_pct_a_year)}</td>
                <td className="tnum py-2 text-right">{r.worst_12m_pct === null ? "–" : pctChange(r.worst_12m_pct)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-caption text-muted">Past results don&apos;t tell you what will happen next.</p>
    </Card>
  );
}

export function ReceiptView({ card }: { card: CardOf<"receipt"> }) {
  return (
    <Card overline={`Practice account · ${month(card.sim_month)}`} title="Your orders are filled">
      <ul className="divide-y divide-line">
        {card.fills.map((f) => (
          <li key={f.product_id} className="flex justify-between gap-3 py-2 text-body-sm">
            <span>
              Bought {f.name}
              <span className="block text-caption text-muted">
                {f.units} units at {moneyCents(f.nav_usd ?? 0)}
              </span>
            </span>
            <span className="tnum">{moneyCents(f.amount_usd)}</span>
          </li>
        ))}
      </ul>
      {card.monthly_usd && (
        <p className="mt-3 text-body-sm text-ink-2">
          Monthly plan: {money(card.monthly_usd)} goes in each month, split the same way.
        </p>
      )}
      <p className="mt-2 break-all font-mono text-caption text-muted">Audit record {card.audit_head.slice(0, 16)}…</p>
    </Card>
  );
}

export function PortfolioView({ card }: { card: CardOf<"portfolio"> }) {
  const gain = Number(card.gain_usd);
  return (
    <Card overline={`Practice account · ${month(card.sim_month)}`}>
      <p className="font-display text-num-hero tnum text-ink">{moneyCents(card.value_usd)}</p>
      <p className="text-body text-ink-2">
        You put in {money(card.paid_in_usd)} ·{" "}
        <span className={gain >= 0 ? "text-primary" : "text-ink"}>{moneyChange(gain)} since you started</span>
      </p>
      {card.max_drift_pts > 0 && (
        <p className="mt-1 text-body-sm text-muted">Furthest from target mix: {card.max_drift_pts.toFixed(0)} points</p>
      )}
      <DataTable
        caption="Holdings"
        head={["Fund", "Value", "Share", "Target"]}
        rows={card.holdings.map((h) => [h.name, moneyCents(h.value_usd), `${h.weight_pct}%`, `${h.target_pct}%`])}
      />
    </Card>
  );
}

export function TermView({ card }: { card: CardOf<"term"> }) {
  return (
    <Card overline="What it means" title={card.term}>
      <p className="text-body text-ink-2">{card.text}</p>
      <a href={card.source_url} target="_blank" rel="noreferrer" className="mt-2 inline-block text-body-sm text-primary underline">
        Source: {card.source_title}
      </a>
    </Card>
  );
}

export function ProductsView({ card }: { card: CardOf<"products"> }) {
  return (
    <Card overline={`Funds for ${card.client_class}`} title="Funds that fit your level">
      <ul className="divide-y divide-line">
        {card.products.map((p) => (
          <li key={p.id} className="flex items-start justify-between gap-3 py-2">
            <div>
              <p className="text-body">{p.name}</p>
              <p className="text-caption text-muted">{p.description}</p>
            </div>
            <span className="shrink-0 font-mono text-caption text-muted">{p.risk_rating}</span>
          </li>
        ))}
      </ul>
      {card.excluded_count > 0 && (
        <p className="mt-2 flex items-start gap-2 text-body-sm text-ink-2">
          <RuleChip id="SUIT-01" /> {card.excluded_count} funds are hidden because they are above your level.
        </p>
      )}
    </Card>
  );
}
