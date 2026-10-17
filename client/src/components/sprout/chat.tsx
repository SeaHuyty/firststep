"use client";

import { SendHorizontal } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/primitives";
import { THINKING } from "@/lib/copy";
import { prefersReducedMotion, wordIntervalMs } from "@/lib/motion";
import type { Card, CardOf } from "@/lib/types";
import { TermView } from "./cards";
import { PLAN_TYPES, View } from "./plan-panel";
import { QuestionView } from "./question";
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

/** Words appear at an even pace; the full text is in the DOM from the start, so the bubble
 * never jumps in size and screen readers get the whole sentence at once. */
function RevealText({ text, onDone, onTick }: { text: string; onDone: () => void; onTick: () => void }) {
  const words = text.split(" ");
  const [count, setCount] = useState(prefersReducedMotion() ? words.length : 0);
  useEffect(() => {
    if (count >= words.length) {
      const t = setTimeout(onDone, 0);
      return () => clearTimeout(t);
    }
    let n = count;
    const timer = setInterval(() => {
      n += 1;
      setCount(n);
      onTick();
      if (n >= words.length) {
        clearInterval(timer);
        onDone();
      }
    }, wordIntervalMs(words.length));
    return () => clearInterval(timer);
    // Run once per text; `count` only seeds the start.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text]);
  return (
    <>
      <span className="sr-only">{text}</span>
      <span aria-hidden>
        {words.slice(0, count).join(" ")}
        <span className="opacity-0"> {words.slice(count).join(" ")}</span>
      </span>
    </>
  );
}

const BUBBLE = "max-w-[60ch] rounded-md rounded-tl-sm border border-line bg-surface px-4 py-3 text-body-lg text-ink";

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
    const inline = <InlineCard card={c} />;
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
          <p className={BUBBLE}>{m.animate ? <RevealText text={spoken} onDone={done} onTick={onTick} /> : spoken}</p>
        )}
        {revealed && blocks.map((b, i) => (m.animate ? <Rise key={i} index={i}>{b}</Rise> : <div key={i}>{b}</div>))}
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex gap-3 animate-fade" role="status">
      <Avatar />
      <p className="flex h-12 items-center gap-1.5 rounded-md rounded-tl-sm border border-line bg-surface px-4">
        <span className="sr-only">{THINKING}</span>
        {[0, 1, 2].map((i) => (
          <span key={i} aria-hidden className="typing-dot size-2 rounded-full bg-primary" />
        ))}
      </p>
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
}: {
  messages: ChatMessage[];
  busy: boolean;
  onAnswer: (questionId: string, value: unknown, label: string) => void;
  hints: Record<string, unknown>;
  onReview: (card: CardOf<"confirm">) => void;
  onShow: (type: string) => void;
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
      {/* The sticky message box sits over the bottom of the page; keep the newest line above it. */}
      <div ref={end} className="scroll-mb-[104px] lg:scroll-mb-2" />
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
