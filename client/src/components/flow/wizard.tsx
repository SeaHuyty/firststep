"use client";

// Onboarding as a guided form: one question per screen, a progress bar by part of the journey,
// options as a list and one Continue button (the pattern of Betterment, Wealthfront and Acorns,
// and the team's sketch). The questions, answers and rules are the server's; this is only how
// they are asked. Results the person has earned (ready to start, a risk level) get their own
// screen before the next part, so the moment is seen rather than scrolled past.
import { ArrowRight } from "lucide-react";
import { type ReactNode, useState } from "react";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/primitives";
import { money } from "@/lib/format";
import type { CardOf } from "@/lib/types";
import { RiskBadgeView } from "@/components/sprout/cards";
import { type Goal, GoalForm } from "@/components/sprout/goal-form";
import { type Answer, DebtsForm, NumberAnswer } from "@/components/sprout/question";

export const PARTS = ["Money check", "Your comfort with risk", "Your goal"] as const;

function same(a: unknown, b: unknown): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

/** Three segments, one per part; the current one fills as its questions are answered. */
export function Progress({ part, fraction }: { part: number; fraction: number }) {
  return (
    <div>
      <ol className="grid grid-cols-3 gap-2" aria-label="Your progress">
        {PARTS.map((name, i) => {
          const fill = i < part ? 1 : i === part ? fraction : 0;
          return (
            <li key={name}>
              <span className="block h-1.5 overflow-hidden rounded-full bg-line" aria-hidden>
                <span className="block h-full rounded-full bg-primary transition-[width] duration-300" style={{ width: `${fill * 100}%` }} />
              </span>
              <span className={`mt-2 hidden text-caption sm:block ${i === part ? "font-semibold text-ink" : "text-muted"}`}>{name}</span>
              <span className="sr-only">{i < part ? " (done)" : i === part ? " (now)" : ""}</span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

/** The frame every onboarding screen shares: progress, a big question, the answer, the action. */
export function Step({
  part,
  fraction,
  overline,
  title,
  children,
}: {
  part: number;
  fraction: number;
  overline: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="mx-auto w-full max-w-xl pb-24 pt-2">
      <Progress part={part} fraction={fraction} />
      <p className="mt-8 text-overline uppercase text-primary">{overline}</p>
      <h1 className="mt-2 font-display text-display-2 text-ink">{title}</h1>
      <div className="mt-6">{children}</div>
    </div>
  );
}

/** A radio list that reads as answers, not a form: big rows, the whole row is the target. */
function Options({
  name,
  options,
  value,
  onChange,
  hint,
}: {
  name: string;
  options: { label: string; value: unknown }[];
  value: string | null;
  onChange: (label: string) => void;
  hint?: unknown;
}) {
  return (
    <div role="radiogroup" aria-label={name} className="space-y-2">
      {options.map((o) => {
        const on = value === o.label;
        return (
          <label
            key={o.label}
            className={`flex min-h-14 cursor-pointer items-center gap-3 rounded-md border px-4 py-3 transition-colors ${on ? "border-primary bg-primary-soft" : "border-line bg-surface hover:border-border-strong"}`}
          >
            <input
              type="radio"
              name={name}
              checked={on}
              onChange={() => onChange(o.label)}
              className="size-5 accent-[var(--color-primary)]"
            />
            <span className="flex-1 text-body-lg text-ink">{o.label}</span>
            {hint !== undefined && same(hint, o.value) && (
              <span className="rounded-full bg-primary-soft px-2 text-caption text-primary">demo answer</span>
            )}
          </label>
        );
      })}
    </div>
  );
}

const TYPE_IT = "Type an exact amount";
const HAVE_DEBTS = "I have debts";

export function QuestionStep({
  card,
  busy,
  hint,
  onAnswer,
}: {
  card: CardOf<"question">;
  busy: boolean;
  hint?: unknown;
  onAnswer: Answer;
}) {
  const part = card.section === "Your comfort with risk" ? 1 : 0;
  const typed = card.kind === "money" || card.kind === "number";
  const options =
    card.kind === "debts"
      ? [{ label: "No debts", value: [] as unknown }, { label: HAVE_DEBTS, value: "__debts" }]
      : [...card.chips, ...(typed ? [{ label: card.kind === "money" ? TYPE_IT : "Type it", value: "__type" }] : [])];
  // Demo people start with their answer selected, so a judge can click straight through.
  const preset = (() => {
    if (hint === undefined) return null;
    if (card.kind === "debts") return Array.isArray(hint) && hint.length > 0 ? HAVE_DEBTS : "No debts";
    const chip = card.chips.find((c) => same(c.value, hint));
    if (chip) return chip.label;
    return typed && typeof hint === "number" ? options.at(-1)?.label ?? null : null;
  })();
  const [picked, setPicked] = useState<string | null>(preset);
  const [why, setWhy] = useState(false);
  const chosen = options.find((o) => o.label === picked);
  const opensForm = chosen?.value === "__type" || chosen?.value === "__debts";
  return (
    <Step part={part} fraction={(card.step - 1) / card.of} overline={`${card.section || "Question"} · ${card.step} of ${card.of}`} title={card.prompt}>
      <Options name={card.prompt} options={options} value={picked} onChange={setPicked} hint={hint} />
      {chosen?.value === "__type" && (
        <div className="mt-4">
          <NumberAnswer card={card} onAnswer={onAnswer} busy={busy} hint={hint} />
        </div>
      )}
      {chosen?.value === "__debts" && (
        <div className="mt-4">
          <DebtsForm card={card} onAnswer={onAnswer} busy={busy} hint={hint} />
        </div>
      )}
      {!opensForm && (
        <Button
          variant="primary"
          className="mt-6 w-full sm:w-auto"
          disabled={!chosen}
          busy={busy}
          busyLabel="Saving…"
          icon={<ArrowRight aria-hidden className="size-5" />}
          onClick={() => chosen && onAnswer(card.question_id, chosen.value, chosen.label)}
        >
          Continue
        </Button>
      )}
      <div className="mt-6">
        <button
          type="button"
          aria-expanded={why}
          onClick={() => setWhy(!why)}
          className="min-h-11 text-label text-primary underline decoration-dotted underline-offset-4"
        >
          Why do we ask?
        </button>
        {why && <p className="mt-1 rounded-sm bg-sunken p-3 text-body text-ink-2">{card.why}</p>}
      </div>
    </Step>
  );
}

/** "You're ready to start": the result of the money check, before the risk questions. */
export function ReadyStep({ card, onNext }: { card: CardOf<"readiness">; onNext: () => void }) {
  return (
    <Step part={1} fraction={0} overline="Money check · done" title="You're ready to start">
      <Notice tone="success" title="Your money check passed">
        Your savings cover {card.emergency_months.toFixed(1)} months of costs, and you have no expensive debt. About{" "}
        {money(card.investable_monthly_usd)} a month is left over.
      </Notice>
      <p className="mt-4 text-body text-ink-2">Next, a few questions about how you feel when markets go up and down.</p>
      <Button variant="primary" className="mt-6" onClick={onNext} icon={<ArrowRight aria-hidden className="size-5" />}>
        Continue
      </Button>
    </Step>
  );
}

/** The risk level, explained, before the goal. */
export function RiskStep({ card, onNext }: { card: CardOf<"risk_badge">; onNext: () => void }) {
  return (
    <Step part={2} fraction={0} overline="Your comfort with risk · done" title="Here's your risk level">
      <RiskBadgeView card={card} />
      <p className="mt-4 text-body text-ink-2">You&apos;ll only see funds that fit this level. Now, what are you investing for?</p>
      <Button variant="primary" className="mt-6" onClick={onNext} icon={<ArrowRight aria-hidden className="size-5" />}>
        Continue
      </Button>
    </Step>
  );
}

export function GoalStep({ initial, busy, onSubmit }: { initial?: Goal | null; busy: boolean; onSubmit: (g: Goal) => void }) {
  return (
    <Step part={2} fraction={0.5} overline="Your goal" title="What are you investing for?">
      <GoalForm initial={initial} busy={busy} onSubmit={onSubmit} />
    </Step>
  );
}
