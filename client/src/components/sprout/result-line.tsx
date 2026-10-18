"use client";

// What a turn changed, said where the person is looking. People miss changes outside their
// focus (NN/g, change blindness), so each plan update also gets one line in the chat, with a
// link that brings the full card into view in the plan pane. Desktop only: on phones the full
// cards already appear in the chat.
import { ArrowRight, CircleCheck, Pause } from "lucide-react";
import type { ReactNode } from "react";
import { RiskBadge } from "@/components/ui/primitives";
import { duration, money, moneyChange, month } from "@/lib/format";
import type { Card } from "@/lib/types";

function Line({
  icon,
  tone = "default",
  children,
  onShow,
}: {
  icon?: ReactNode;
  tone?: "default" | "success" | "pause";
  children: ReactNode;
  onShow: () => void;
}) {
  const box =
    tone === "success"
      ? "border-primary bg-primary-soft"
      : tone === "pause"
        ? "border-sun bg-sun-soft"
        : "border-line bg-surface";
  return (
    <div className={`flex items-center gap-3 rounded-md border px-4 py-2 ${box}`}>
      {icon}
      <p className="min-w-0 flex-1 text-body text-ink">{children}</p>
      <button
        type="button"
        onClick={onShow}
        className="inline-flex min-h-11 shrink-0 items-center gap-1 rounded-sm px-2 text-label text-primary hover:bg-primary-soft"
      >
        See in plan <ArrowRight aria-hidden className="size-4" />
      </button>
    </div>
  );
}

const OK = <CircleCheck aria-hidden className="size-5 shrink-0 text-primary" />;
const PAUSE = <Pause aria-hidden className="size-5 shrink-0 text-sun-ink" />;

/** One line for a plan card, or null for cards that are shown in full in the chat. */
export function ResultLine({ card, onShow }: { card: Card; onShow: () => void }) {
  switch (card.type) {
    case "readiness":
      return card.ready ? (
        <Line icon={OK} tone="success" onShow={onShow}>
          You&apos;re ready to start: {card.emergency_months.toFixed(1)} months of savings, no expensive debt.
        </Line>
      ) : (
        <Line icon={PAUSE} tone="pause" onShow={onShow}>
          Not yet: {card.reasons.length === 2 ? "expensive debt and a thin safety cushion" : card.reasons[0]?.rule_id === "READY-02" ? "expensive debt first" : "a safety cushion first"}.
        </Line>
      );
    case "savings_plan":
      if (card.steps.length === 0) {
        return <Line icon={PAUSE} tone="pause" onShow={onShow}>Your plan: first, find a little room each month.</Line>;
      }
      return (
        <Line icon={OK} onShow={onShow}>
          Your plan: {card.steps.length} {card.steps.length === 1 ? "step" : "steps"}
          {card.ready_month && card.months_to_ready !== null
            ? `, ready to invest by ${month(card.ready_month)} (${duration(card.months_to_ready)})`
            : ""}
          .
        </Line>
      );
    case "risk_badge":
      return (
        <Line onShow={onShow}>
          Your risk level: <RiskBadge code={card.client_class} label={card.label} />
        </Line>
      );
    case "goal":
      return (
        <Line onShow={onShow}>
          Goal saved: {money(card.target_usd)} in {card.horizon_years} years.
        </Line>
      );
    case "allocation":
      return (
        <Line onShow={onShow}>
          Plan: {card.label}, {money(card.total_usd)} across {card.lines.length} funds, about{" "}
          {money(card.fee_usd_a_year)} a year in fees.
        </Line>
      );
    case "projection": {
      const end = card.years.length - 1;
      return (
        <Line onShow={onShow}>
          After {card.years[end]} years: {money(card.p10[end] ?? 0)} to {money(card.p90[end] ?? 0)}, typically{" "}
          {money(card.p50[end] ?? 0)}.
        </Line>
      );
    }
    case "receipt":
      return (
        <Line icon={OK} tone="success" onShow={onShow}>
          {card.fills.length} orders filled for {money(card.fills.reduce((sum, f) => sum + Number(f.amount_usd), 0))}
          {card.monthly_usd ? `, then ${money(card.monthly_usd)} a month` : ""}.
        </Line>
      );
    case "portfolio":
      return (
        <Line onShow={onShow}>
          {month(card.sim_month)}: worth {money(card.value_usd)}, {moneyChange(card.gain_usd)} since you started.
        </Line>
      );
    case "comparison":
    {
      const mine = card.rows.find((r) => r.in_plan);
      return (
        <Line onShow={onShow}>
          {mine ? `Compared ${mine.name} with ${card.rows.length - 1} similar ${card.rows.length === 2 ? "fund" : "funds"}.` : `Compared ${card.rows.length} funds side by side.`}
        </Line>
      );
    }
    case "products":
      return <Line onShow={onShow}>{card.products.length} funds fit your level.</Line>;
    default:
      return null;
  }
}

/** The plan card a turn most needs to show: one change at a time (NN/g). */
export const SPOTLIGHT_ORDER = [
  "receipt",
  "portfolio",
  "savings_plan",
  "readiness",
  "allocation",
  "projection",
  "risk_badge",
  "goal",
  "comparison",
  "products",
] as const;
