"use client";

// One session, two shapes. Until the plan exists it is a guided form: one question per screen
// (components/flow/wizard.tsx). After that it is a dashboard with a sidebar: Home, Plan, Funds
// and Activity (components/app/dashboard.tsx). Sprout is always one tap away as a floating
// chat. Every tap and every typed message still goes through the same API, tools and guardian.
import { RotateCcw } from "lucide-react";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Notice, Skeleton } from "@/components/ui/primitives";
import { AppShell } from "@/components/ui/shell";
import { type Action, api } from "@/lib/api";
import { STEP_OF } from "@/lib/copy";
import { withTypingDelay } from "@/lib/motion";
import type { Card, CardOf, PersonaHint, SessionView, Stage, TurnOut } from "@/lib/types";
import {
  ActivityView,
  FundsView,
  HomeView,
  LatestNote,
  Nav,
  PlanView,
  type Product,
  type View,
  latestByType,
} from "@/components/app/dashboard";
import { GoalStep, QuestionStep, ReadyStep, RiskStep } from "@/components/flow/wizard";
import { Assistant } from "./assistant";
import { type ChatMessage, Composer, MessageList } from "./chat";
import { ConfirmDialog } from "./confirm-dialog";
import type { Goal } from "./goal-form";
import { PlanActionsContext } from "./plan-actions";
import { GlossaryProvider } from "./term";

const ONBOARDING = new Set<Stage>(["ONBOARD", "READINESS", "PROFILE", "GOAL"]);
const NOTICE_TYPES = new Set(["refusal", "pause", "alert"]);

const PLACEHOLDER: Partial<Record<Stage, string>> = {
  PROPOSE: "Ask, e.g. \"What is a bond?\"",
  MONITOR: "Ask about your plan",
  SAVINGS_PLAN: "Ask about your savings plan",
};

type Catalog = { products: Product[]; max_rating_for_class: Record<string, string> };

function useCatalog() {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  useEffect(() => {
    let live = true;
    fetch("/api/catalog")
      .then((r) => (r.ok ? r.json() : null))
      .then((c: Catalog | null) => live && c && setCatalog(c))
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, []);
  return catalog;
}

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
  const [page, setPage] = useState<View>("home");
  const [fundFilter, setFundFilter] = useState("all");
  const [chatOpen, setChatOpen] = useState(false);
  const [auditKey, setAuditKey] = useState(0);
  // Result screens ("You're ready", "Your risk level") already seen, by message id.
  const [seen, setSeen] = useState<Set<number>>(new Set());
  const catalog = useCatalog();
  const nextId = useRef(1);
  const newId = () => nextId.current++;

  const fetchSession = useCallback(
    () =>
      api.session(id).then(
        (v) => {
          setView(v);
          const loaded: ChatMessage[] = v.messages.map((m, i) => ({
            id: -1 - i,
            role: m.role === "user" ? "user" : "sprout",
            text: m.text,
            cards: m.cards,
          }));
          setMessages(loaded);
          // A reloaded session goes straight to where it was, not back through result screens.
          setSeen(new Set(loaded.map((m) => m.id)));
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
    // Orders ready: open the check-before-you-confirm dialog straight away.
    const confirm = out.cards.filter((c): c is CardOf<"confirm"> => c.type === "confirm").at(-1);
    if (confirm) setReviewing(confirm);
  };

  const run = async (call: () => Promise<TurnOut>, userText?: string) => {
    if (busy) return;
    setTurnError(null);
    if (userText) setMessages((m) => [...m, { id: newId(), role: "user", text: userText, cards: [], animate: true }]);
    setBusy(true);
    try {
      apply(await withTypingDelay(call));
    } catch (e) {
      setTurnError({ message: (e as Error).message, retry: () => void run(call) });
    } finally {
      setBusy(false);
    }
  };

  const act = (action: Action, label?: string) => run(() => api.act(id, { ...action, label }), label);
  const say = (text: string) => run(() => api.say(id, text), text);
  const compare = (ids: string[], label: string) => act({ tool: "compare_products", args: { product_ids: ids } }, label);
  const planActions = { compare, busy };

  const persona: PersonaHint | null | undefined = view?.persona;
  const hints = useMemo(() => (persona?.answers ?? {}) as Record<string, unknown>, [persona]);
  const allCards = messages.flatMap((m) => m.cards);
  const latest = latestByType(allCards);
  const lastSprout = messages.filter((m) => m.role === "sprout").at(-1);
  const lastCards = lastSprout?.cards ?? [];
  const driftAlert = lastCards.some((c) => c.type === "alert" && c.rule_id === "DRIFT-01");

  // "See in plan" from the chat: close the chat and open the page that shows it.
  const show = (type: string) => {
    setChatOpen(false);
    setPage(type === "comparison" ? "funds" : type === "readiness" || type === "portfolio" || type === "receipt" ? "home" : "plan");
  };

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

  const errorNote = turnError && (
    <div className="mb-6">
      <Notice tone="error" title="That didn't go through" action={<Button onClick={turnError.retry}>Try again</Button>}>
        {turnError.message}
      </Notice>
    </div>
  );

  // --- onboarding: one screen at a time
  let screen: React.ReactNode = null;
  if (ONBOARDING.has(stage)) {
    const fresh = lastSprout && !seen.has(lastSprout.id);
    const ready = fresh ? lastCards.find((c): c is CardOf<"readiness"> => c.type === "readiness" && c.ready) : undefined;
    const risk = fresh ? lastCards.find((c): c is CardOf<"risk_badge"> => c.type === "risk_badge") : undefined;
    const question = lastCards.filter((c): c is CardOf<"question"> => c.type === "question").at(-1);
    const done = () => lastSprout && setSeen(new Set([...seen, lastSprout.id]));
    if (ready) screen = <ReadyStep card={ready} onNext={done} />;
    else if (risk) screen = <RiskStep card={risk} onNext={done} />;
    else if (stage === "GOAL")
      screen = (
        <GoalStep
          initial={(persona?.goal as Goal | null | undefined) ?? null}
          busy={busy}
          onSubmit={(g) => act({ tool: "set_goal", args: g }, `${g.name}: $${g.target_usd.toLocaleString("en-US")} in ${g.horizon_years} years`)}
        />
      );
    else if (question)
      screen = (
        <QuestionStep
          key={question.question_id}
          card={question}
          busy={busy}
          hint={hints[question.question_id]}
          onAnswer={(qid, value, label) => act({ tool: "answer_question", args: { question_id: qid, value } }, label)}
        />
      );
    else screen = <Skeleton className="mx-auto h-64 w-full max-w-xl" />;
  }

  const notices = lastCards.filter((c: Card) => NOTICE_TYPES.has(c.type));
  const chat = (
    <Assistant
      open={chatOpen}
      onOpen={() => setChatOpen(true)}
      onClose={() => setChatOpen(false)}
      unread={false}
      composer={
        <Composer onSend={say} busy={busy} placeholder={PLACEHOLDER[stage] ?? "Ask Sprout something"} />
      }
    >
      <MessageList
        messages={messages}
        busy={busy}
        hints={hints}
        ask={false}
        onAnswer={(qid, value, label) => act({ tool: "answer_question", args: { question_id: qid, value } }, label)}
        onReview={setReviewing}
        onShow={show}
      />
    </Assistant>
  );

  return (
    <GlossaryProvider>
      <PlanActionsContext.Provider value={planActions}>
        <AppShell step={STEP_OF[stage]}>
          {persona && (
            <p className="mb-4 max-w-none text-body-sm text-ink-2">
              Demo as <strong>{persona.name}</strong>, {persona.tagline.split(",")[0]}.{" "}
              {ONBOARDING.has(stage) ? "Continue with the marked answers." : "Try every page, or ask Sprout."}
            </p>
          )}
          {screen ? (
            <>
              {errorNote}
              {screen}
            </>
          ) : (
            // Room under the content for the floating "Ask Sprout" (and the tab bar on phones).
            <div className="pb-36 lg:flex lg:gap-8 lg:pb-24">
              <Nav view={page} onView={setPage} />
              <main className="min-w-0 flex-1">
                {errorNote}
                {page !== "activity" && <LatestNote reply={lastSprout?.text ?? ""} notices={notices} onOpenChat={() => setChatOpen(true)} />}
                {page === "home" && (
                  <HomeView
                    stage={stage}
                    latest={latest}
                    allCards={allCards}
                    simMonth={simMonth}
                    busy={busy}
                    driftAlert={driftAlert}
                    onView={setPage}
                    onPrepare={() => act({ tool: "prepare_orders" }, "Review the orders")}
                    onReview={setReviewing}
                    onAdvance={(args) => act({ tool: "advance_time", args }, args.until ? "Jump to March 2020" : args.months === 12 ? "Fast-forward a year" : "Fast-forward a month")}
                    onRebalance={() => act({ tool: "propose_rebalance" }, "Show me a rebalance")}
                  />
                )}
                {page === "plan" && (
                  <PlanView
                    stage={stage}
                    latest={latest}
                    busy={busy}
                    onFunds={(family) => {
                      setFundFilter(family);
                      setPage("funds");
                    }}
                    onPrepare={() => act({ tool: "prepare_orders" }, "Review the orders")}
                    onReview={setReviewing}
                  />
                )}
                {page === "funds" && (
                  <FundsView
                    stage={stage}
                    products={catalog?.products ?? []}
                    latest={latest}
                    maxRating={latest.risk_badge ? (catalog?.max_rating_for_class[latest.risk_badge.client_class] ?? null) : null}
                    busy={busy}
                    filter={fundFilter}
                    onFilter={setFundFilter}
                    onCompare={compare}
                    onSwap={(out, inn, label) => {
                      const lines = (latest.allocation?.lines ?? []).map((l) => ({
                        product_id: l.product_id === out ? inn : l.product_id,
                        weight_pct: l.weight_pct,
                      }));
                      void act({ tool: "propose_custom_allocation", args: { lines } }, label).then(() => setPage("plan"));
                    }}
                  />
                )}
                {page === "activity" && <ActivityView sessionId={id} refreshKey={auditKey} />}
              </main>
            </div>
          )}
          {chat}
          {reviewing && (
            <ConfirmDialog
              card={reviewing}
              open={reviewing !== null}
              busy={busy}
              onClose={() => setReviewing(null)}
              onConfirm={() => {
                const pid = reviewing.proposal_id;
                void run(() => api.confirm(id, pid), "Confirm").then(() => {
                  setReviewing(null);
                  setPage("home");
                });
              }}
            />
          )}
        </AppShell>
      </PlanActionsContext.Provider>
    </GlossaryProvider>
  );
}

export function SessionSkeleton() {
  return (
    <AppShell step={null}>
      <div className="mx-auto max-w-xl space-y-4">
        <Skeleton className="h-2 w-full" />
        <Skeleton className="h-12 w-3/4" />
        <Skeleton className="h-14 w-full" />
        <Skeleton className="h-14 w-full" />
        <Skeleton className="h-14 w-full" />
      </div>
    </AppShell>
  );
}
