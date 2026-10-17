"use client";

import { RotateCcw } from "lucide-react";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Notice, Skeleton } from "@/components/ui/primitives";
import { AppShell } from "@/components/ui/shell";
import { type Action, api } from "@/lib/api";
import { STEP_OF } from "@/lib/copy";
import type { CardOf, PersonaHint, SessionView, Stage, TurnOut } from "@/lib/types";
import { type ChatMessage, Composer, MessageList } from "./chat";
import { ConfirmDialog } from "./confirm-dialog";
import { type Goal, GoalForm } from "./goal-form";
import { AuditPanel, PlanPanel, WatchControls } from "./plan-panel";

type Tab = "chat" | "plan" | "audit";

const PLACEHOLDER: Partial<Record<Stage, string>> = {
  PROPOSE: "Ask about your plan, e.g. \"What does diversification mean?\"",
  MONITOR: "Ask Sprout anything about your plan",
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
  const [auditKey, setAuditKey] = useState(0);
  const [auditOpen, setAuditOpen] = useState(false);

  const fetchSession = useCallback(
    () =>
      api.session(id).then(
        (v) => {
          setView(v);
          setMessages(v.messages.map((m) => ({ role: m.role === "user" ? "user" : "sprout", text: m.text, cards: m.cards })));
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
    setMessages((m) => [...m, { role: "sprout", text: out.reply, cards: out.cards, steps: out.steps }]);
    setStage(out.stage as Stage);
    setSimMonth(out.sim_month);
    setAuditKey((k) => k + 1);
  };

  const run = async (call: () => Promise<TurnOut>, userText?: string) => {
    if (busy) return;
    setTurnError(null);
    if (userText) setMessages((m) => [...m, { role: "user", text: userText, cards: [] }]);
    setBusy(true);
    try {
      apply(await call());
    } catch (e) {
      setTurnError({ message: (e as Error).message, retry: () => void run(call) });
    } finally {
      setBusy(false);
    }
  };

  const act = (action: Action, label?: string) => run(() => api.act(id, action), label);
  const say = (text: string) => run(() => api.say(id, text), text);

  const persona: PersonaHint | null | undefined = view?.persona;
  const hints = useMemo(() => (persona?.answers ?? {}) as Record<string, unknown>, [persona]);
  const allCards = messages.flatMap((m) => m.cards);
  const lastCards = messages.at(-1)?.cards ?? [];
  const driftAlert = lastCards.some((c) => c.type === "alert" && c.rule_id === "DRIFT-01");
  const hasPlan = allCards.some((c) => c.type === "projection");

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

  const chat = (
    <div className="flex flex-col gap-4">
      <MessageList
        messages={messages}
        busy={busy}
        hints={hints}
        onAnswer={(qid, value, label) => act({ tool: "answer_question", args: { question_id: qid, value } }, label)}
        onReview={setReviewing}
      />
      {turnError && (
        <Notice tone="error" title="That didn't go through" action={<Button onClick={turnError.retry}>Try again</Button>}>
          {turnError.message}
        </Notice>
      )}
      {stage === "GOAL" && !busy && (
        <GoalForm
          initial={(persona?.goal as Goal | null | undefined) ?? null}
          busy={busy}
          onSubmit={(g) => act({ tool: "set_goal", args: g }, `${g.name}: $${g.target_usd.toLocaleString("en-US")} in ${g.horizon_years} years`)}
        />
      )}
      {stage === "PROPOSE" && hasPlan && !busy && (
        <Button variant="primary" onClick={() => act({ tool: "prepare_orders" }, "Review the orders")}>
          Review the orders
        </Button>
      )}
      <div className="sticky bottom-3 z-10 mt-2">
        <Composer onSend={say} busy={busy} placeholder={PLACEHOLDER[stage] ?? "Ask Sprout, or tap an answer above"} />
      </div>
    </div>
  );

  const plan = (
    <div className="space-y-4">
      {(stage === "EXECUTED" || stage === "MONITOR") && (
        <WatchControls
          simMonth={simMonth}
          busy={busy}
          driftAlert={driftAlert}
          onAdvance={(args) => act({ tool: "advance_time", args }, args.until ? "Jump to March 2020" : args.months === 12 ? "Fast-forward a year" : "Fast-forward a month")}
          onRebalance={() => act({ tool: "propose_rebalance" }, "Show me a rebalance")}
        />
      )}
      <PlanPanel cards={allCards} stage={stage} />
    </div>
  );

  return (
    <AppShell step={STEP_OF[stage]}>
      {persona && (
        <p className="mb-4 text-body-sm text-ink-2">
          Demo: you are <strong>{persona.name}</strong>, {persona.tagline}. Suggested answers are marked.
        </p>
      )}
      <div role="tablist" aria-label="View" className="mb-4 flex gap-1 rounded-md bg-sunken p-1 lg:hidden">
        {(["chat", "plan", "audit"] as const).map((t) => (
          <button
            key={t}
            role="tab"
            type="button"
            aria-selected={tab === t}
            onClick={() => setTab(t)}
            className={`min-h-11 flex-1 rounded-sm text-label ${tab === t ? "bg-surface text-ink shadow-popover" : "text-ink-2"}`}
          >
            {t === "chat" ? "Chat" : t === "plan" ? "My plan" : "Audit log"}
          </button>
        ))}
      </div>
      <div className="lg:grid lg:grid-cols-12 lg:gap-8">
        <section aria-label="Chat with Sprout" className={`lg:col-span-5 ${tab === "chat" ? "" : "hidden lg:block"}`}>
          {chat}
        </section>
        <section aria-label="My plan" className={`lg:col-span-7 ${tab === "plan" ? "" : "hidden lg:block"}`}>
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
