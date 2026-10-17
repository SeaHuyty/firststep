"use client";

// One question at a time, always with tappable answers, so nobody has to know what to type
// (docs/standards/onboarding-ux.md principles 1-2; Hick's law in docs/ux-psychology.md).
import { Check } from "lucide-react";
import { useId, useState } from "react";
import { Button } from "@/components/ui/button";
import type { CardOf } from "@/lib/types";

type Answer = (questionId: string, value: unknown, label: string) => void;

function same(a: unknown, b: unknown): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

export function QuestionView({
  card,
  onAnswer,
  busy,
  hint,
  showPrompt = true,
}: {
  card: CardOf<"question">;
  onAnswer: Answer;
  busy: boolean;
  hint?: unknown;
  /** False when the chat already "spoke" the prompt as Sprout's message. */
  showPrompt?: boolean;
}) {
  const [showWhy, setShowWhy] = useState(false);
  return (
    <div className="space-y-3">
      {showPrompt && (
        <p className="max-w-[60ch] rounded-md rounded-tl-sm border border-line bg-surface px-4 py-3 text-body-lg text-ink">
          {card.prompt}
        </p>
      )}
      <div className="flex items-center justify-between gap-3">
        <p className="text-caption text-muted">
          Question {card.step} of {card.of}
        </p>
        <button
          type="button"
          onClick={() => setShowWhy(!showWhy)}
          aria-expanded={showWhy}
          className="min-h-11 text-label text-primary underline decoration-dotted underline-offset-4"
        >
          Why do you ask?
        </button>
      </div>
      {showWhy && <p className="rounded-sm bg-sunken p-3 text-body-sm text-ink-2">{card.why}</p>}
      {card.kind !== "debts" && (
        <div className="flex flex-wrap gap-2" role="group" aria-label={card.prompt}>
          {card.chips.map((chip) => {
            const suggested = hint !== undefined && same(hint, chip.value);
            return (
              <button
                key={chip.label}
                type="button"
                disabled={busy}
                onClick={() => onAnswer(card.question_id, chip.value, chip.label)}
                className="inline-flex min-h-11 items-center gap-2 rounded-full border-[1.5px] border-primary bg-surface px-4 text-label text-primary transition-colors hover:bg-primary-soft active:translate-y-px disabled:opacity-40"
              >
                {chip.label}
                {suggested && <span className="rounded-full bg-primary-soft px-2 text-caption">demo answer</span>}
              </button>
            );
          })}
        </div>
      )}
      {(card.kind === "money" || card.kind === "number") && (
        <NumberAnswer card={card} onAnswer={onAnswer} busy={busy} hint={hint} />
      )}
      {card.kind === "debts" && <DebtsAnswer card={card} onAnswer={onAnswer} busy={busy} hint={hint} />}
    </div>
  );
}

function NumberAnswer({ card, onAnswer, busy, hint }: { card: CardOf<"question">; onAnswer: Answer; busy: boolean; hint?: unknown }) {
  const id = useId();
  const [value, setValue] = useState(typeof hint === "number" ? String(hint) : "");
  const money = card.kind === "money";
  const n = Number(value.replace(/[$,\s]/g, ""));
  const valid = value.trim() !== "" && Number.isFinite(n) && n >= 0;
  return (
    <form
      className="flex flex-wrap items-end gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        if (valid) onAnswer(card.question_id, n, money ? `$${n.toLocaleString("en-US")}` : String(n));
      }}
    >
      <div>
        <label htmlFor={id} className="block text-label text-ink-2">
          {money ? "Or type an amount" : "Or type it"}
        </label>
        <div className="mt-2 flex items-center rounded-sm border border-border-strong bg-surface focus-within:border-2 focus-within:border-primary">
          {money && <span className="pl-3 text-muted">$</span>}
          <input
            id={id}
            inputMode="decimal"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            className="h-12 w-36 bg-transparent px-3 outline-none"
          />
        </div>
      </div>
      <Button variant="secondary" disabled={!valid || busy} type="submit">
        Save
      </Button>
    </form>
  );
}

type Debt = { kind: string; balance_usd: number; apr_pct: number };
const KINDS = [
  ["credit_card", "Credit card"],
  ["personal_loan", "Personal loan"],
  ["student_loan", "Student loan"],
  ["car_loan", "Car loan"],
] as const;

function DebtsAnswer({ card, onAnswer, busy, hint }: { card: CardOf<"question">; onAnswer: Answer; busy: boolean; hint?: unknown }) {
  const preset = Array.isArray(hint) ? (hint as Debt[]) : [];
  const [debts, setDebts] = useState<Debt[]>(preset);
  const [kind, setKind] = useState<string>("credit_card");
  const [balance, setBalance] = useState("");
  const [apr, setApr] = useState("");
  const ids = { kind: useId(), balance: useId(), apr: useId() };
  const b = Number(balance.replace(/[$,\s]/g, ""));
  const a = Number(apr.replace(/[%\s]/g, ""));
  const canAdd = balance !== "" && apr !== "" && b > 0 && a >= 0 && a <= 100;
  return (
    <div className="space-y-3">
      <Button variant="secondary" disabled={busy} onClick={() => onAnswer(card.question_id, [], "No debts")}>
        No debts
      </Button>
      <fieldset className="rounded-md border border-line p-3">
        <legend className="px-1 text-label text-ink-2">Or add each debt</legend>
        <div className="flex flex-wrap items-end gap-2">
          <div>
            <label htmlFor={ids.kind} className="block text-label text-ink-2">Type</label>
            <select id={ids.kind} value={kind} onChange={(e) => setKind(e.target.value)} className="mt-2 h-12 rounded-sm border border-border-strong bg-surface px-3">
              {KINDS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </div>
          <div>
            <label htmlFor={ids.balance} className="block text-label text-ink-2">You owe ($)</label>
            <input id={ids.balance} inputMode="decimal" value={balance} onChange={(e) => setBalance(e.target.value)} className="mt-2 h-12 w-28 rounded-sm border border-border-strong bg-surface px-3" />
          </div>
          <div>
            <label htmlFor={ids.apr} className="block text-label text-ink-2">Yearly rate (%)</label>
            <input id={ids.apr} inputMode="decimal" value={apr} onChange={(e) => setApr(e.target.value)} className="mt-2 h-12 w-24 rounded-sm border border-border-strong bg-surface px-3" />
          </div>
          <Button
            variant="ghost"
            disabled={!canAdd}
            onClick={() => {
              setDebts([...debts, { kind, balance_usd: b, apr_pct: a }]);
              setBalance("");
              setApr("");
            }}
          >
            Add
          </Button>
        </div>
        {debts.length > 0 && (
          <ul className="mt-3 space-y-1 text-body-sm text-ink-2">
            {debts.map((d, i) => (
              <li key={i} className="flex items-center gap-2">
                <Check aria-hidden className="size-4 text-primary" />
                {KINDS.find(([v]) => v === d.kind)?.[1] ?? d.kind}: ${d.balance_usd.toLocaleString("en-US")} at {d.apr_pct}% a year
              </li>
            ))}
          </ul>
        )}
      </fieldset>
      {debts.length > 0 && (
        <Button variant="primary" busy={busy} busyLabel="Saving…" onClick={() => onAnswer(card.question_id, debts, debts.length === 1 ? "I have 1 debt" : `I have ${debts.length} debts`)}>
          Save {debts.length === 1 ? "this debt" : `these ${debts.length} debts`}
        </Button>
      )}
    </div>
  );
}
