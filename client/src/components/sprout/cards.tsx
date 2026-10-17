"use client";

// One view per card type the server sends. Formatting only: no finance happens here.
import { useState } from "react";
import { Card, DataTable, Notice, RiskBadge, RuleChip } from "@/components/ui/primitives";
import { RuleNote } from "@/components/ui/rule-note";
import { FAMILY_LABEL } from "@/lib/copy";
import { duration, money, moneyCents, month, pctChange } from "@/lib/format";
import type { CardOf } from "@/lib/types";
import { AllocationDonut, FamilyDot, ProjectionFan } from "./charts";
import { Term } from "./term";

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
      <ul className="mt-1 list-disc space-y-1 pl-5">
        {card.reasons.map((r) => (
          <li key={r.rule_id ?? r.text}>{r.text}</li>
        ))}
      </ul>
      <RuleNote ids={card.reasons.flatMap((r) => (r.rule_id ? [r.rule_id] : []))} />
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
      <RiskBadge code={card.client_class} label={card.label} />
      <p className="mt-2 text-body text-ink">{card.summary}</p>
      <p className="mt-2 text-body text-ink-2">
        In its worst 12 months since 2000, a plan at this level{" "}
        {card.worst_12m_pct < 0 ? `fell about ${Math.abs(card.worst_12m_pct).toFixed(0)}%` : "still grew a little"}. In its best,
        it grew about {card.best_12m_pct.toFixed(0)}%.
      </p>
      <dl className="mt-3 grid grid-cols-2 gap-3 text-body-sm">
        <div className="rounded-sm bg-sunken p-3">
          <dt className="text-muted">Your comfort with ups and downs</dt>
          <dd className="text-num-card tnum">{card.tolerance} of 5</dd>
        </div>
        <div className="rounded-sm bg-sunken p-3">
          <dt className="text-muted">Room to absorb a loss</dt>
          <dd className="text-num-card tnum">{card.capacity} of 5</dd>
        </div>
      </dl>
      <p className="mt-2 text-body-sm text-ink-2">Sprout uses the lower of the two, to be careful.</p>
      <div className="mt-1">
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
        <>
          <p className="mt-2 text-body-sm text-ink-2">A short goal keeps your plan at {card.client_class} or below.</p>
          <RuleNote ids={["HOR-01"]} />
        </>
      )}
    </Card>
  );
}

const FAMILY_MEANING: Record<string, { term: string; text: string }> = {
  cash: { term: "emergency_fund", text: "holds steady, for money you might need soon" },
  bonds: { term: "bond", text: "loans to governments that pay interest, with small ups and downs" },
  stocks: { term: "index_fund", text: "small pieces of thousands of companies; grows most over years, but can drop" },
  gold: { term: "diversification", text: "often moves differently from stocks" },
};

export function AllocationView({ card }: { card: CardOf<"allocation"> }) {
  const parts = Object.entries(card.families).filter(([, w]) => w > 0);
  return (
    <Card overline={`Your plan · ${card.client_class} ${card.label.split(" ").slice(1).join(" ")}`} title={`What your ${money(card.total_usd)} is made of`}>
      {/* The words are the legend: each part says what it is for, next to its colour. */}
      <AllocationDonut families={card.families} total={card.total_usd}>
        <ul className="w-full space-y-3">
          {parts.map(([family, weight]) => {
            const meaning = FAMILY_MEANING[family];
            return (
              <li key={family} className="flex gap-2 text-body text-ink-2">
                <FamilyDot family={family} />
                <span>
                  <strong className="text-ink">{Math.round(weight)}% in {meaning ? <Term id={meaning.term}>{FAMILY_LABEL[family]?.toLowerCase()}</Term> : FAMILY_LABEL[family]}</strong>
                  {meaning ? `: ${meaning.text}.` : "."}
                </span>
              </li>
            );
          })}
        </ul>
      </AllocationDonut>
      <div className="mt-4 rounded-sm bg-sunken p-3 text-body text-ink-2">
        <p>
          <strong className="text-ink">The honest part:</strong> in its worst 12 months since 2000, a mix like this would
          have turned your {money(card.total_usd)} into about {money(card.worst_12m_usd)}. In its best, about{" "}
          {money(card.best_12m_usd)}. Nobody knows which comes next.
        </p>
      </div>
      <p className="mt-3 text-body text-ink-2">
        <Term id="fee">Fees</Term>: about {money(card.fee_usd_a_year)} a year for all {card.lines.length} funds together.
      </p>
      <details className="mt-3">
        <summary className="min-h-11 cursor-pointer py-2 text-label text-primary">See the {card.lines.length} funds</summary>
        <ul className="divide-y divide-line">
          {card.lines.map((l) => (
            <li key={l.product_id} className="py-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-body text-ink">{l.name}</p>
                  <p className="text-caption text-muted">
                    {FAMILY_LABEL[l.family]} · <Term id="risk_rating">risk {l.risk_rating}</Term>
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
      </details>
    </Card>
  );
}

/** 100 dots: how many of 100 replays of past markets ended year one below the money put in.
 * Icon arrays and "X out of 100" help people with low numeracy understand risk (Galesic,
 * Garcia-Retamero and Gigerenzer 2009); see docs/ux-psychology.md. */
function IconArray({ below }: { below: number }) {
  return (
    <div className="grid w-40 shrink-0 grid-cols-10 gap-1" role="img" aria-label={`${below} out of 100 dots marked`}>
      {Array.from({ length: 100 }, (_, i) => (
        <span key={i} className={`size-3 rounded-full ${i < below ? "bg-sun" : "bg-primary/25"}`} />
      ))}
    </div>
  );
}

export function ProjectionView({ card }: { card: CardOf<"projection"> }) {
  const end = card.years.length - 1;
  const p10 = card.p10[end] ?? 0;
  const p50 = card.p50[end] ?? 0;
  const p90 = card.p90[end] ?? 0;
  const paid = card.paid_in[end] ?? 0;
  const below = Math.round(card.prob_below_paid_in_year1 * 100);
  const reach = card.prob_reach_goal === null ? null : Math.round(card.prob_reach_goal * 100);
  return (
    <Card overline="What could happen" title={`In ${card.years[end]} years, if you stick with the plan`}>
      <p className="text-body text-ink-2">You would put in {money(paid)} in total.</p>
      <dl className="mt-3 grid gap-2 sm:grid-cols-3">
        <div className="rounded-sm bg-sunken p-3">
          <dt className="text-body-sm text-muted">In a bad case</dt>
          <dd className="text-num-card tnum text-ink">{money(p10)}</dd>
          <dd className="text-caption text-ink-2">{p10 >= paid ? "still more than you put in" : `${money(paid - p10)} less than you put in`}</dd>
        </div>
        <div className="rounded-sm border-2 border-primary bg-primary-soft p-3">
          <dt className="text-body-sm text-muted">Most likely</dt>
          <dd className="text-num-card tnum text-ink">{money(p50)}</dd>
          <dd className="text-caption text-ink-2">{p50 >= paid ? `${money(p50 - paid)} more than you put in` : "about what you put in"}</dd>
        </div>
        <div className="rounded-sm bg-sunken p-3">
          <dt className="text-body-sm text-muted">In a good case</dt>
          <dd className="text-num-card tnum text-ink">{money(p90)}</dd>
          <dd className="text-caption text-ink-2">{money(p90 - paid)} more than you put in</dd>
        </div>
      </dl>
      <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center">
        <IconArray below={below} />
        <p className="text-body text-ink-2">
          We replayed <Term id="outcome_range">past markets</Term> 5,000 times. Out of every 100 replays,{" "}
          <strong className="text-ink">{below}</strong> ended the first year below what was put in (amber dots).
          {reach !== null && card.goal_usd !== null && ` ${reach} out of 100 reached your ${money(card.goal_usd)} goal.`}
        </p>
      </div>
      <details className="mt-3">
        <summary className="min-h-11 cursor-pointer py-2 text-label text-primary">See it year by year</summary>
        <ProjectionFan years={card.years} p10={card.p10} p50={card.p50} p90={card.p90} paidIn={card.paid_in} />
      </details>
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
  const total = card.fills.reduce((sum, f) => sum + Number(f.amount_usd), 0);
  return (
    <Card overline={`Practice account · ${month(card.sim_month)}`} title={`Your ${money(total)} is invested`}>
      <ul className="space-y-1 text-body text-ink-2">
        {card.fills.map((f) => (
          <li key={f.product_id} className="flex justify-between gap-3">
            <span>{f.name}</span>
            <span className="tnum text-ink">{money(f.amount_usd)}</span>
          </li>
        ))}
      </ul>
      {card.monthly_usd && (
        <p className="mt-3 text-body text-ink-2">
          From next month, {money(card.monthly_usd)} goes in automatically, split the same way.
        </p>
      )}
      <p className="mt-2 text-body-sm text-ink-2">This is practice money. Nothing real was bought.</p>
      <details className="mt-2">
        <summary className="min-h-11 cursor-pointer py-2 text-label text-primary">Details</summary>
        <ul className="divide-y divide-line text-body-sm">
          {card.fills.map((f) => (
            <li key={f.product_id} className="flex justify-between gap-3 py-2">
              <span>
                {f.name}
                <span className="block text-caption text-muted">
                  {f.units} units at {moneyCents(f.nav_usd ?? 0)} each
                </span>
              </span>
              <span className="tnum">{moneyCents(f.amount_usd)}</span>
            </li>
          ))}
        </ul>
        <p className="mt-2 break-all font-mono text-caption text-muted">Audit record {card.audit_head.slice(0, 16)}…</p>
      </details>
    </Card>
  );
}

export function PortfolioView({ card }: { card: CardOf<"portfolio"> }) {
  const gain = Number(card.gain_usd);
  return (
    <Card overline={`Practice account · ${month(card.sim_month)}`}>
      <p className="font-display text-num-hero tnum text-ink">{money(card.value_usd)}</p>
      <p className="text-body text-ink-2">
        You put in {money(card.paid_in_usd)}.{" "}
        {gain >= 0 ? (
          <span className="text-primary">That&apos;s {money(gain)} more.</span>
        ) : (
          <span>That&apos;s {money(-gain)} below for now. Drops like this usually pass with time.</span>
        )}
      </p>
      {card.max_drift_pts > 5 && (
        <p className="mt-1 text-body-sm text-muted">
          Your mix has drifted from its target, <Term id="rebalancing">rebalancing</Term> can fix that.
        </p>
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
        <>
          <p className="mt-2 text-body-sm text-ink-2">{card.excluded_count} funds are hidden because they are above your level.</p>
          <RuleNote ids={["SUIT-01"]} />
        </>
      )}
    </Card>
  );
}
