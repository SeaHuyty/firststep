"use client";

import { RotateCcw } from "lucide-react";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Notice, Skeleton } from "@/components/ui/primitives";
import { AppShell } from "@/components/ui/shell";
import { type Action, api } from "@/lib/api";
import { STEP_OF } from "@/lib/copy";
import { withTypingDelay } from "@/lib/motion";
import type { CardOf, PersonaHint, SessionView, Stage, TurnOut } from "@/lib/types";
import { type ChatMessage, Composer, MessageList } from "./chat";
import { ConfirmDialog } from "./confirm-dialog";
import { type Goal, GoalForm } from "./goal-form";
import { AuditPanel, PlanPanel, WatchControls } from "./plan-panel";
import { SPOTLIGHT_ORDER } from "./result-line";
import { Safeguards } from "./safeguards";
import { GlossaryProvider } from "./term";

type Tab = "chat" | "plan" | "audit";

const PLACEHOLDER: Partial<Record<Stage, string>> = {
  // Short enough for one line on a phone.
  PROPOSE: "Ask, e.g. \"What is a bond?\"",
  MONITOR: "Ask about your plan",
  SAVINGS_PLAN: "Ask about your savings plan",
};

export function SessionScreen() {
  const { id } = useParams<{ id: string }>();
  const [view, setView] = useState<SessionView | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [stage, setStage] = useState<Stage>("ONBOARD");
  const [simMonth, setSimMonth] = useState("");
  const [busy, setBusy] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [turnError, setTurnError] = useState<{ message: string; retry: () => void } | null>(null);
  const [reviewing, setReviewing] = useState<CardOf<"confirm"> | null>(null);
  const [tab, setTab] = useState<Tab>("chat");
  // Phones show one view at a time on one scrolling page: the chat opens at its newest line,
  // the plan and the audit log at their top, not at whatever offset the last view had.
  const showTab = (t: Tab) => {
    setTab(t);
    requestAnimationFrame(() => {
      if (t === "chat") document.querySelector("[data-chat-end]")?.scrollIntoView({ block: "end" });
      else window.scrollTo({ top: 0 });
    });
  };
  const [auditKey, setAuditKey] = useState(0);
  const [auditOpen, setAuditOpen] = useState(false);
  const [spotlight, setSpotlight] = useState<{ type: string; n: number } | null>(null);
  const showInPlan = (type: string) => setSpotlight((prev) => ({ type, n: (prev?.n ?? 0) + 1 }));
  const nextId = useRef(1);
  const newId = () => nextId.current++;

  const fetchSession = useCallback(
    () =>
      api.session(id).then(
        (v) => {
          setView(v);
          setMessages(
            v.messages.map((m, i) => ({ id: -1 - i, role: m.role === "user" ? "user" : "sprout", text: m.text, cards: m.cards })),
          );
          setStage(v.stage as Stage);
          setSimMonth(v.sim_month);
        },
        (e: Error) => setLoadError(e.message),
      ),
    [id],
  );

  useEffect(() => {
    void fetchSession();
  }, [fetchSession]);

  const retryLoad = () => {
    setLoadError(null);
    void fetchSession();
  };

  const apply = (out: TurnOut) => {
    setMessages((m) => [...m, { id: newId(), role: "sprout", text: out.reply, cards: out.cards, steps: out.steps, animate: true }]);
    setStage(out.stage as Stage);
    setSimMonth(out.sim_month);
    setAuditKey((k) => k + 1);
    // Bring the turn's most important plan change into view (one change at a time).
    const changed = SPOTLIGHT_ORDER.find((t) => out.cards.some((c) => c.type === t));
    if (changed) showInPlan(changed);
  };

  const run = async (call: () => Promise<TurnOut>, userText?: string) => {
    if (busy) return;
    setTurnError(null);
    if (userText) setMessages((m) => [...m, { id: newId(), role: "user", text: userText, cards: [], animate: true }]);
    setBusy(true);
    try {
      // A short, length-scaled pause with the typing indicator (capped at 1 s; none when the
      // request itself took longer). See docs/ux-psychology.md.
      apply(await withTypingDelay(call));
    } catch (e) {
      setTurnError({ message: (e as Error).message, retry: () => void run(call) });
    } finally {
      setBusy(false);
    }
  };

  const act = (action: Action, label?: string) => run(() => api.act(id, { ...action, label }), label);
  const say = (text: string) => run(() => api.say(id, text), text);

  const persona: PersonaHint | null | undefined = view?.persona;
  const hints = useMemo(() => (persona?.answers ?? {}) as Record<string, unknown>, [persona]);
  const allCards = messages.flatMap((m) => m.cards);
  const lastCards = messages.at(-1)?.cards ?? [];
  const driftAlert = lastCards.some((c) => c.type === "alert" && c.rule_id === "DRIFT-01");
  const hasPlan = allCards.some((c) => c.type === "projection");
  // Sprout is waiting for an answer to a question (or the goal form): that is the next step.
  const asking = !busy && (lastCards.some((c) => c.type === "question") || stage === "GOAL");

  if (loadError) {
    return (
      <AppShell step={null}>
        <Notice tone="error" title="We couldn't open this session" action={<Button onClick={retryLoad} icon={<RotateCcw aria-hidden className="size-5" />}>Try again</Button>}>
          {loadError}
        </Notice>
      </AppShell>
    );
  }
  if (!view) return <SessionSkeleton />;

  // What to do next sits at the end of the chat, and the chat follows it into view.
  const chatBody = (
    <div className="pb-2">
      <MessageList
        messages={messages}
        busy={busy}
        hints={hints}
        onAnswer={(qid, value, label) => act({ tool: "answer_question", args: { question_id: qid, value } }, label)}
        onReview={setReviewing}
        onShow={showInPlan}
      >
      {turnError && (
        <Notice tone="error" title="That didn't go through" action={<Button onClick={turnError.retry}>Try again</Button>}>
          {turnError.message}
        </Notice>
      )}
      {stage === "GOAL" && !busy && (
        <div className="animate-rise">
          <GoalForm
            initial={(persona?.goal as Goal | null | undefined) ?? null}
            busy={busy}
            onSubmit={(g) => act({ tool: "set_goal", args: g }, `${g.name}: $${g.target_usd.toLocaleString("en-US")} in ${g.horizon_years} years`)}
          />
        </div>
      )}
      {stage === "PROPOSE" && hasPlan && !busy && (
        <div className="animate-rise">
          <Button variant="primary" onClick={() => act({ tool: "prepare_orders" }, "Review the orders")}>
            Review the orders
          </Button>
        </div>
      )}
      {(stage === "EXECUTED" || stage === "MONITOR") && (
        <div className="animate-rise">
          <WatchControls
            simMonth={simMonth}
            busy={busy}
            driftAlert={driftAlert}
            onAdvance={(args) => act({ tool: "advance_time", args }, args.until ? "Jump to March 2020" : args.months === 12 ? "Fast-forward a year" : "Fast-forward a month")}
            onRebalance={() => act({ tool: "propose_rebalance" }, "Show me a rebalance")}
          />
        </div>
      )}
      </MessageList>
    </div>
  );

  const plan = (
    <div className="space-y-4">
      <Safeguards cards={allCards} stage={stage} />
      <PlanPanel cards={allCards} stage={stage} spotlight={spotlight} />
    </div>
  );

  // Desktop is a workspace: chat and plan side by side, each scrolling on its own, with the
  // message box pinned under the chat, so neither pushes the other off-screen (the split-pane
  // pattern of Claude Artifacts and ChatGPT Canvas). Phones keep tabs and one scrolling page.
  return (
    <GlossaryProvider>
    <AppShell step={STEP_OF[stage]} fill>
      {persona && (
        <p className="mb-4 max-w-none text-body-sm text-ink-2 lg:mb-3">
          Demo as <strong>{persona.name}</strong>, {persona.tagline.split(",")[0]}. Tap the marked answers.
        </p>
      )}
      <div role="tablist" aria-label="View" className="mb-4 flex gap-1 rounded-md bg-sunken p-1 lg:hidden">
        {(["chat", "plan", "audit"] as const).map((t) => (
          <button
            key={t}
            role="tab"
            type="button"
            aria-selected={tab === t}
            onClick={() => showTab(t)}
            className={`min-h-11 flex-1 rounded-sm text-label ${tab === t ? "bg-surface text-ink shadow-popover" : "text-ink-2"}`}
          >
            {t === "chat" ? "Chat" : t === "plan" ? "My plan" : "Audit log"}
          </button>
        ))}
      </div>
      <div className="lg:grid lg:min-h-0 lg:flex-1 lg:grid-cols-12 lg:gap-8">
        <section
          aria-label="Chat with Sprout"
          className={`lg:col-span-5 lg:flex lg:min-h-0 lg:flex-col ${tab === "chat" ? "" : "hidden lg:flex"}`}
        >
          <div data-scroll-root className="lg:min-h-0 lg:flex-1 lg:overflow-y-auto lg:pr-2">
            {chatBody}
          </div>
          <div className="sticky bottom-3 z-10 mt-2 lg:static lg:mt-3">
            <Composer
              onSend={say}
              busy={busy}
              quiet={asking}
              placeholder={asking ? "Or ask Sprout something" : (PLACEHOLDER[stage] ?? "Ask Sprout something")}
            />
          </div>
        </section>
        <section
          aria-label="My plan"
          data-plan-scroll
          className={`lg:col-span-7 lg:min-h-0 lg:overflow-y-auto lg:pr-2 ${tab === "plan" ? "" : "hidden lg:block"}`}
        >
          {plan}
          <details className="mt-4 hidden lg:block" onToggle={(e) => setAuditOpen(e.currentTarget.open)}>
            <summary className="min-h-11 cursor-pointer py-2 text-label text-primary">See the audit log</summary>
            {auditOpen && <AuditPanel sessionId={id} refreshKey={auditKey} />}
          </details>
        </section>
        {tab === "audit" && (
          <section aria-label="Audit log" className="lg:hidden">
            <AuditPanel sessionId={id} refreshKey={auditKey} />
          </section>
        )}
      </div>
      {reviewing && (
        <ConfirmDialog
          card={reviewing}
          open={reviewing !== null}
          busy={busy}
          onClose={() => setReviewing(null)}
          onConfirm={() => {
            const pid = reviewing.proposal_id;
            void run(() => api.confirm(id, pid), "Confirm").then(() => setReviewing(null));
          }}
        />
      )}
    </AppShell>
    </GlossaryProvider>
  );
}

export function SessionSkeleton() {
  return (
    <AppShell step={null}>
      <div className="lg:grid lg:grid-cols-12 lg:gap-8">
        <div className="space-y-4 lg:col-span-5">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-12 w-2/3" />
          <Skeleton className="h-12 w-1/2" />
        </div>
        <div className="mt-6 space-y-4 lg:col-span-7 lg:mt-0">
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      </div>
    </AppShell>
  );
}
