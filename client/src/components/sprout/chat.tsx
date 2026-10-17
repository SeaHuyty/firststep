"use client";

import { SendHorizontal } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/primitives";
import { prefersReducedMotion } from "@/lib/motion";
import type { Card, CardOf } from "@/lib/types";
import { TermView } from "./cards";
import { PLAN_TYPES, View } from "./plan-panel";
import { QUESTION, QuestionView } from "./question";
import { Avatar, BUBBLE, RevealText, TypingIndicator } from "./bubble";
import { ResultLine } from "./result-line";

export type ChatMessage = {
  id: number;
  role: "user" | "sprout";
  text: string;
  cards: Card[];
  steps?: string[];
  /** True for messages that arrive now (typed in); false for history loaded on refresh. */
  animate?: boolean;
};

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

const squash = (t: string) => t.replace(/\s+/g, " ").trim().toLowerCase();

/** `said`: Sprout's reply already says the card's sentence, so the card keeps only its title. */
function InlineCard({ card, said }: { card: Card; said: string }) {
  const body = (text: string) => (said && squash(said).includes(squash(text)) ? null : text);
  switch (card.type) {
    case "refusal": {
      const text = [body(card.text), card.next_step].filter(Boolean).join(" ");
      return (
        <Notice tone="error" title={card.title} ruleId={card.rule_id}>
          {text || null}
        </Notice>
      );
    }
    case "pause":
      return <Notice tone="pause" title={card.title} ruleId={card.rule_id}>{body(card.text)}</Notice>;
    case "alert":
      return (
        <Notice tone={card.tone === "pause" ? "pause" : "info"} title={card.title} ruleId={card.rule_id}>
          {body(card.text)}
        </Notice>
      );
    case "term":
      return <TermView card={card} />;
    default:
      return null;
  }
}

function Rise({ index, children }: { index: number; children: React.ReactNode }) {
  return (
    <div className="animate-rise" style={{ animationDelay: `${index * 60}ms` }}>
      {children}
    </div>
  );
}

function SproutTurn({
  m,
  isLast,
  busy,
  onAnswer,
  hints,
  onReview,
  onTick,
  onShow,
}: {
  m: ChatMessage;
  isLast: boolean;
  busy: boolean;
  onAnswer: (questionId: string, value: unknown, label: string) => void;
  hints: Record<string, unknown>;
  onReview: (card: CardOf<"confirm">) => void;
  onTick: () => void;
  onShow: (type: string) => void;
}) {
  const questions = m.cards.filter((c): c is CardOf<"question"> => c.type === "question");
  const asking = isLast && !busy ? questions.at(-1) : undefined;
  // With no reply of its own, Sprout "says" the next question, then the chips appear.
  const spoken = m.text || asking?.prompt || "";
  const [revealed, setRevealed] = useState(!m.animate || !spoken);
  const done = () => setRevealed(true);
  // Follow once the cards and chips have actually rendered, not before.
  useEffect(() => {
    if (revealed && m.animate) onTick();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [revealed]);
  const blocks: React.ReactNode[] = [];
  if (m.steps && m.steps.length > 0) {
    blocks.push(
      <p key="steps" className="text-caption text-muted">
        {m.steps.map((s) => STEP_LABEL[s]).filter(Boolean).join(" · ")}
      </p>,
    );
  }
  m.cards.forEach((c, j) => {
    const inline = <InlineCard card={c} said={m.text} />;
    if (c.type === "refusal" || c.type === "pause" || c.type === "alert" || c.type === "term") {
      blocks.push(<div key={`i${j}`}>{inline}</div>);
    }
  });
  // On narrow screens the plan builds inside the chat too, so the key moments (the "not yet"
  // plan, the range of outcomes) are never on a hidden tab.
  const planCards = m.cards.filter((c) => PLAN_TYPES.has(c.type));
  if (planCards.length > 0) {
    blocks.push(
      <div key="plan" className="space-y-3 lg:hidden">
        {planCards.map((c, j) => <View key={j} card={c} />)}
      </div>,
    );
    // Desktop: the full cards live in the plan pane; say what changed here, where the reader
    // is looking, with a link to it (NN/g on change blindness).
    blocks.push(
      <div key="results" className="hidden space-y-2 lg:block">
        {planCards.map((c, j) => <ResultLine key={j} card={c} onShow={() => onShow(c.type)} />)}
      </div>,
    );
  }
  if (isLast) {
    m.cards
      .filter((c): c is CardOf<"confirm"> => c.type === "confirm")
      .slice(-1)
      .forEach((c) =>
        blocks.push(
          <Button key={c.proposal_id} variant="primary" onClick={() => onReview(c)} disabled={busy}>
            Review {c.orders.length === 1 ? "the order" : `${c.orders.length} orders`}
          </Button>,
        ),
      );
  }
  if (asking) {
    blocks.push(
      <QuestionView
        key={asking.question_id}
        card={asking}
        onAnswer={onAnswer}
        busy={busy}
        hint={hints[asking.question_id]}
        showPrompt={Boolean(m.text)}
      />,
    );
  } else {
    // Answered questions stay as Sprout's words, so the history reads as a conversation.
    questions.forEach((q) =>
      blocks.push(
        <p key={q.question_id} className={BUBBLE}>
          {q.prompt}
        </p>,
      ),
    );
  }
  return (
    <div className="flex gap-3">
      <Avatar />
      <div className="min-w-0 flex-1 space-y-3">
        {spoken && (
          <p className={!m.text && asking ? QUESTION : BUBBLE}>
            {m.animate ? <RevealText text={spoken} onDone={done} onTick={onTick} /> : spoken}
          </p>
        )}
        {revealed && blocks.map((b, i) => (m.animate ? <Rise key={i} index={i}>{b}</Rise> : <div key={i}>{b}</div>))}
      </div>
    </div>
  );
}

export function MessageList({
  messages,
  busy,
  onAnswer,
  hints,
  onReview,
  onShow,
  children,
}: {
  messages: ChatMessage[];
  busy: boolean;
  onAnswer: (questionId: string, value: unknown, label: string) => void;
  hints: Record<string, unknown>;
  onReview: (card: CardOf<"confirm">) => void;
  onShow: (type: string) => void;
  /** The next step (a form, a button), after the messages and inside what the chat follows. */
  children?: React.ReactNode;
}) {
  const end = useRef<HTMLDivElement>(null);
  // Follow new content only while the reader is near the bottom; if they scrolled up to reread,
  // leave them there. A new turn of their own always brings them back.
  const stick = useRef(true);
  useEffect(() => {
    // The chat scrolls inside its own pane on desktop and with the page on phones.
    const pane = end.current?.closest<HTMLElement>("[data-scroll-root]") ?? null;
    const onScroll = () => {
      const el = end.current;
      if (!el) return;
      const scrolling = pane && pane.scrollHeight > pane.clientHeight ? pane : null;
      const bottom = scrolling ? scrolling.getBoundingClientRect().bottom : window.innerHeight;
      stick.current = el.getBoundingClientRect().top - bottom < 240;
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    pane?.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      pane?.removeEventListener("scroll", onScroll);
    };
  }, []);
  const follow = () => {
    if (stick.current) {
      end.current?.scrollIntoView({ behavior: prefersReducedMotion() ? "auto" : "smooth", block: "end" });
    }
  };
  useEffect(() => {
    if (busy) stick.current = true;
    follow();
  }, [messages.length, busy]);
  const lastSprout = messages.map((m) => m.role).lastIndexOf("sprout");
  return (
    <div className="space-y-4" aria-live="polite">
      {messages.map((m, i) =>
        m.role === "user" ? (
          <div key={m.id} className={`flex justify-end ${m.animate ? "animate-rise" : ""}`}>
            <p className="max-w-[60ch] rounded-md rounded-br-sm bg-primary px-4 py-2 text-body-lg text-on-primary">{m.text}</p>
          </div>
        ) : (
          <SproutTurn
            key={m.id}
            m={m}
            isLast={i === lastSprout}
            busy={busy}
            onAnswer={onAnswer}
            hints={hints}
            onReview={onReview}
            onTick={follow}
            onShow={onShow}
          />
        ),
      )}
      {busy && <TypingIndicator />}
      {children}
      {/* The sticky message box sits over the bottom of the page; keep the newest line above it. */}
      <div ref={end} data-chat-end className="scroll-mb-[104px] lg:scroll-mb-2" />
    </div>
  );
}

/** The message box. While Sprout waits for a tap it steps back (no shadow, softer edge) so the
 * answers are the obvious next step; typing is still there for questions. */
export function Composer({
  onSend,
  busy,
  placeholder,
  quiet = false,
}: {
  onSend: (text: string) => void;
  busy: boolean;
  placeholder: string;
  quiet?: boolean;
}) {
  const [text, setText] = useState("");
  const id = useId();
  return (
    <form
      className={`flex items-end gap-2 rounded-md border bg-surface p-2 transition-shadow duration-[var(--duration-base)] focus-within:border-border-strong focus-within:shadow-popover ${quiet ? "border-line" : "border-border-strong shadow-popover"}`}
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
