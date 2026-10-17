"use client";

// The goal step. Pre-filled with a sensible default (defaults matter: docs/ux-psychology.md),
// and the horizon rule is shown as the slider moves so nothing about the cap is a surprise.
import { useId, useState } from "react";
import { Button } from "@/components/ui/button";
import { RuleChip } from "@/components/ui/primitives";
import { money } from "@/lib/format";

const GOALS = ["Long-term growth", "House deposit", "Retirement top-up", "Rainy-day growth"];

export type Goal = {
  name: string;
  target_usd: number;
  horizon_years: number;
  lump_sum_usd: number;
  monthly_usd: number;
};

const DEFAULT: Goal = { name: "Long-term growth", target_usd: 30000, horizon_years: 10, lump_sum_usd: 2000, monthly_usd: 200 };

function MoneyInput({ label, value, onChange }: { label: string; value: number; onChange: (n: number) => void }) {
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className="block text-label text-ink-2">{label}</label>
      <div className="mt-2 flex items-center rounded-sm border border-border-strong bg-surface focus-within:border-2 focus-within:border-primary">
        <span className="pl-3 text-muted">$</span>
        <input
          id={id}
          inputMode="numeric"
          value={value.toLocaleString("en-US")}
          onChange={(e) => onChange(Number(e.target.value.replace(/[^\d.]/g, "")) || 0)}
          className="tnum h-12 w-full bg-transparent px-3 outline-none"
        />
      </div>
    </div>
  );
}

export function GoalForm({ initial, onSubmit, busy }: { initial?: Goal | null; onSubmit: (g: Goal) => void; busy: boolean }) {
  const [goal, setGoal] = useState<Goal>(initial ?? DEFAULT);
  const yearsId = useId();
  const set = <K extends keyof Goal>(key: K, value: Goal[K]) => setGoal({ ...goal, [key]: value });
  const capNote =
    goal.horizon_years < 1
      ? "Under 1 year keeps you at C1."
      : goal.horizon_years < 3
        ? "Under 3 years keeps you at C2 or below."
        : null;
  return (
    <form
      className="mt-3 space-y-6"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit(goal);
      }}
    >
      <div role="group" aria-label="What are you investing for?" className="flex flex-wrap gap-2">
        {GOALS.map((g) => (
          <button
            key={g}
            type="button"
            aria-pressed={goal.name === g}
            onClick={() => set("name", g)}
            className={`min-h-11 rounded-full border-[1.5px] border-primary px-4 text-label ${goal.name === g ? "bg-primary text-on-primary" : "bg-surface text-primary hover:bg-primary-soft"}`}
          >
            {g}
          </button>
        ))}
      </div>
      <div className="grid gap-6 sm:grid-cols-3">
        <MoneyInput label="Target" value={goal.target_usd} onChange={(n) => set("target_usd", n)} />
        <MoneyInput label="Put in now" value={goal.lump_sum_usd} onChange={(n) => set("lump_sum_usd", n)} />
        <MoneyInput label="Each month" value={goal.monthly_usd} onChange={(n) => set("monthly_usd", n)} />
      </div>
      <div>
        <label htmlFor={yearsId} className="flex justify-between text-label text-ink-2">
          <span>How long until you need it?</span>
          <span className="tnum text-ink">{goal.horizon_years} years</span>
        </label>
        <input
          id={yearsId}
          type="range"
          min={1}
          max={40}
          value={goal.horizon_years}
          onChange={(e) => set("horizon_years", Number(e.target.value))}
          className="mt-3 h-11 w-full accent-[var(--color-primary)]"
        />
        <p className="mt-1 flex min-h-6 items-center gap-2 text-body-sm text-ink-2">
          {capNote ? (
            <>
              <RuleChip id="HOR-01" /> {capNote}
            </>
          ) : (
            "A longer time lets your plan ride out more ups and downs."
          )}
        </p>
      </div>
      <Button variant="primary" type="submit" busy={busy} busyLabel="Building your plan…" disabled={goal.target_usd <= 0}>
        Build my plan with {money(goal.lump_sum_usd)} now
      </Button>
    </form>
  );
}
