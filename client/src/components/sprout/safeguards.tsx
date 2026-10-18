"use client";

// "Your safeguards": the protections around this person, ticking on as each one applies.
// Seeing the protective structures is what makes people willing to trust an unfamiliar
// system ("structural assurance", McKnight, Choudhury and Kacmar 2002); for robo-advice,
// visible competence and integrity drive trust (docs/research/ux-psychology.md).
import { Check, ChevronDown, Circle, ShieldCheck } from "lucide-react";
import { RuleChip } from "@/components/ui/primitives";
import type { Card, Stage } from "@/lib/types";

type Item = { done: boolean; text: string; rule?: string };

function items(cards: Card[], stage: Stage): Item[] {
  const has = (t: Card["type"]) => cards.some((c) => c.type === t);
  const readiness = cards.find((c): c is Extract<Card, { type: "readiness" }> => c.type === "readiness");
  const risk = cards.filter((c): c is Extract<Card, { type: "risk_badge" }> => c.type === "risk_badge").at(-1);
  const watching = stage === "EXECUTED" || stage === "MONITOR";
  return [
    { done: true, text: "Practice money only. No real money moves." },
    readiness && !readiness.ready
      ? { done: true, text: "Sprout said “not yet”: debts and savings come first.", rule: "READY-01" }
      : { done: Boolean(readiness), text: "Your savings and debts are checked before any investing.", rule: "READY-01" },
    {
      done: Boolean(risk),
      text: risk ? `You only see funds that fit your level (${risk.client_class} ${risk.label}).` : "You'll only see funds that fit your risk level.",
      rule: "SUIT-01",
    },
    { done: has("allocation"), text: "Your money is spread out, never too much in one fund.", rule: "CONC-01" },
    {
      done: has("receipt"),
      text: has("receipt") ? "Nothing was bought until you pressed Confirm." : "Nothing is bought until you press Confirm.",
      rule: "CONF-01",
    },
    { done: watching, text: "A big sale right after a drop waits 24 hours, so a scare can't decide for you.", rule: "COOL-01" },
    { done: true, text: "Every step is recorded in a log that can be checked." },
  ];
}

/**
 * One line that is always visible, "Safeguards: 2 of 7 in place" with a pip per safeguard, and
 * the full list one click away (progressive disclosure). The structure stays in sight without
 * a block of text competing with the question (docs/research/ux-psychology.md, "One focal point").
 */
export function Safeguards({ cards, stage }: { cards: Card[]; stage: Stage }) {
  const list = items(cards, stage);
  const on = list.filter((it) => it.done).length;
  return (
    <details className="group rounded-md border border-line bg-surface">
      <summary className="flex min-h-11 cursor-pointer list-none items-center gap-3 px-4 py-3 [&::-webkit-details-marker]:hidden">
        <ShieldCheck aria-hidden className="size-5 shrink-0 text-primary" />
        <span className="text-label text-ink">
          Your safeguards: {on} of {list.length} in place
        </span>
        <span aria-hidden className="ml-auto hidden gap-1 sm:flex">
          {list.map((it) => (
            <span key={it.text} className={`size-2 rounded-full ${it.done ? "bg-primary" : "bg-line"}`} />
          ))}
        </span>
        <ChevronDown aria-hidden className="size-4 shrink-0 text-muted transition-transform group-open:rotate-180 max-sm:ml-auto" />
      </summary>
      <ul className="space-y-2 border-t border-line px-4 py-3">
        {list.map((it) => (
          <li key={it.text} className="flex items-start gap-2 text-body-sm">
            {it.done ? (
              <Check aria-hidden className="mt-0.5 size-4 shrink-0 text-primary" />
            ) : (
              <Circle aria-hidden className="mt-0.5 size-4 shrink-0 text-border-strong" />
            )}
            <span className={it.done ? "text-ink" : "text-muted"}>
              {it.text}
              <span className="sr-only">{it.done ? " (in place)" : " (later in your plan)"}</span>
            </span>
            {it.rule && it.done && <span className="ml-auto hidden xl:inline"><RuleChip id={it.rule} /></span>}
          </li>
        ))}
      </ul>
    </details>
  );
}
