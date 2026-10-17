"use client";

import { SendHorizontal } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/primitives";
import { THINKING } from "@/lib/copy";
import type { Card, CardOf } from "@/lib/types";
import { TermView } from "./cards";
import { PLAN_TYPES, View } from "./plan-panel";
import { QuestionView } from "./question";

export type ChatMessage = { role: "user" | "sprout"; text: string; cards: Card[]; steps?: string[] };

const STEP_LABEL: Record<string, string> = {
  assess_readiness: "Checked your savings and debts",
  build_savings_plan: "Built a savings plan",
  score_risk_profile: "Worked out your risk level",
  set_goal: "Saved your goal",
  propose_allocation: "Picked funds that fit your level",
  propose_custom_allocation: "Checked your mix against the rules",
  project_outcomes: "Replayed past markets",
  prepare_orders: "Prepared the orders",
  place_order: "Placed the orders",
  advance_time: "Moved time forward",
  request_sell: "Checked the sale against the rules",
  propose_rebalance: "Worked out a rebalance",
  explain: "Looked up the definition",
};

function Avatar() {
  // eslint-disable-next-line @next/next/no-img-element -- a 32px SVG avatar
  return <img src="/brand/sprout-avatar.svg" alt="" width={32} height={32} className="mt-1 size-8 shrink-0" />;
}

function InlineCard({ card }: { card: Card }) {
  switch (card.type) {
    case "refusal":
      return (
        <Notice tone="error" title={card.title} ruleId={card.rule_id}>
          {card.text} {card.next_step}
        </Notice>
      );
    case "pause":
      return <Notice tone="pause" title={card.title} ruleId={card.rule_id}>{card.text}</Notice>;
    case "alert":
      return (
        <Notice tone={card.tone === "pause" ? "pause" : "info"} title={card.title} ruleId={card.rule_id}>
          {card.text}
        </Notice>
      );
    case "term":
      return <TermView card={card} />;
    default:
      return null;
  }
}

export function MessageList({
  messages,
  busy,
  onAnswer,
  hints,
  onReview,
}: {
  messages: ChatMessage[];
  busy: boolean;
  onAnswer: (questionId: string, value: unknown, label: string) => void;
  hints: Record<string, unknown>;
  onReview: (card: CardOf<"confirm">) => void;
}) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    // A block body: newer browsers return a Promise from scrollIntoView, which must not become
    // the effect's cleanup.
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, busy]);
  const lastSprout = messages.map((m) => m.role).lastIndexOf("sprout");
  return (
    <div className="space-y-4" aria-live="polite">
      {messages.map((m, i) =>
        m.role === "user" ? (
          <div key={i} className="flex justify-end">
            <p className="max-w-[60ch] rounded-md rounded-br-sm bg-primary px-4 py-2 text-body-lg text-on-primary">{m.text}</p>
          </div>
        ) : (
          <div key={i} className="flex gap-3">
            <Avatar />
            <div className="min-w-0 flex-1 space-y-3">
              {m.text && (
                <p className="max-w-[60ch] rounded-md rounded-tl-sm border border-line bg-surface px-4 py-3 text-body-lg text-ink">{m.text}</p>
              )}
              {m.steps && m.steps.length > 0 && (
                <p className="text-caption text-muted">
                  {m.steps.map((s) => STEP_LABEL[s]).filter(Boolean).join(" · ")}
                </p>
              )}
              {m.cards.map((c, j) => <InlineCard key={j} card={c} />)}
              {/* On narrow screens the plan builds inside the chat too, so the key moments
                  (the "not yet" plan, the range of outcomes) are never on a hidden tab. */}
              <div className="space-y-3 lg:hidden">
                {m.cards.filter((c) => PLAN_TYPES.has(c.type)).map((c, j) => <View key={j} card={c} />)}
              </div>
              {i === lastSprout &&
                m.cards
                  .filter((c): c is CardOf<"confirm"> => c.type === "confirm")
                  .slice(-1)
                  .map((c) => (
                    <Button key={c.proposal_id} variant="primary" onClick={() => onReview(c)} disabled={busy}>
                      Review {c.orders.length === 1 ? "the order" : `${c.orders.length} orders`}
                    </Button>
                  ))}
              {/* Answered questions stay as Sprout's words, so the history reads as a conversation. */}
              {(i !== lastSprout || busy) &&
                m.cards
                  .filter((c): c is CardOf<"question"> => c.type === "question")
                  .map((q) => (
                    <p key={q.question_id} className="max-w-[60ch] rounded-md rounded-tl-sm border border-line bg-surface px-4 py-3 text-body-lg text-ink">
                      {q.prompt}
                    </p>
                  ))}
              {i === lastSprout &&
                !busy &&
                m.cards
                  .filter((c): c is CardOf<"question"> => c.type === "question")
                  .slice(-1)
                  .map((q) => <QuestionView key={q.question_id} card={q} onAnswer={onAnswer} busy={busy} hint={hints[q.question_id]} />)}
            </div>
          </div>
        ),
      )}
      {busy && (
        <div className="flex gap-3" role="status">
          <Avatar />
          <p className="animate-pulse rounded-md border border-line bg-surface px-4 py-3 text-body text-muted">{THINKING}</p>
        </div>
      )}
      <div ref={end} />
    </div>
  );
}

export function Composer({ onSend, busy, placeholder }: { onSend: (text: string) => void; busy: boolean; placeholder: string }) {
  const [text, setText] = useState("");
  const id = useId();
  return (
    <form
      className="flex items-end gap-2 rounded-md border border-border-strong bg-surface p-2 shadow-popover"
      onSubmit={(e) => {
        e.preventDefault();
        const t = text.trim();
        if (!t || busy) return;
        onSend(t);
        setText("");
      }}
    >
      <label htmlFor={id} className="sr-only">Message Sprout</label>
      <textarea
        id={id}
        rows={1}
        maxLength={1000}
        value={text}
        placeholder={placeholder}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            e.currentTarget.form?.requestSubmit();
          }
        }}
        className="max-h-32 min-h-11 flex-1 resize-none bg-transparent px-2 py-2.5 outline-none placeholder:text-muted"
      />
      <Button type="submit" variant="ghost" disabled={busy || !text.trim()} aria-label="Send" icon={<SendHorizontal aria-hidden className="size-5" />}>
        <span className="sr-only">Send</span>
      </Button>
    </form>
  );
}
