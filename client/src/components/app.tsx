"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useCatalog } from "@/lib/catalog";
import { defaultProfile, groupOf, type Market, type Pct, type PlanResult, type ProductGroup, type Profile, type Risk } from "@/lib/types";
import { Advisor, type AdvisorHandle } from "./advisor";
import { useStocks } from "@/lib/use-stocks";
import { PlanPage, type Pick } from "./plan";
import { AnalysisStep, InfoStep, Loading } from "./steps";

const steps = ["Enter Your Information", "AI Analysis", "Your Plan"];

// Amount edits don't change the plan, so a result stays valid across them.
const keyOf = (p: Profile) => JSON.stringify({ ...p, amount: 0 });

export default function App() {
  const catalog = useCatalog();
  const [step, setStep] = useState(0);
  const [profile, setProfile] = useState<Profile>(defaultProfile);
  const [confirmed, setConfirmed] = useState<(keyof Profile)[]>([]);
  const [override, setOverride] = useState<{ pct: Pct; key: string; reason: string } | null>(null);
  // Groups the advisor or the client has adjusted, with the funds they kept or added (ticker -> why). Other groups
  // keep the system's suggestions. Valid only at the risk level they were made for.
  const [chosen, setChosen] = useState<{ risk: Risk; groups: ProductGroup[]; items: Record<string, Pick> } | null>(null);
  const [advisorOpen, setAdvisorOpen] = useState(false);
  const advisor = useRef<AdvisorHandle>(null);
  const [market, setMarket] = useState<Market | null>(null);
  const [planState, setPlanState] = useState<{ key: string; data: PlanResult } | null>(null);

  const profileKey = keyOf(profile);

  useEffect(() => {
    api.market().then(setMarket, () => setMarket({ source: "", asof: null, items: {} }));
  }, []);

  useEffect(() => {
    const ctrl = new AbortController();
    const timer = setTimeout(() => {
      api.plan(profile, ctrl.signal).then(
        (data) => setPlanState({ key: keyOf(profile), data }),
        () => {},
      );
    }, 200);
    return () => {
      clearTimeout(timer);
      ctrl.abort();
    };
  }, [profile]);

  // Keep showing the last plan while a new one loads, so editing the amount or risk never blanks the page.
  const plan = planState?.data ?? null;
  const stale = planState?.key !== profileKey;
  const active = override && override.key === profileKey ? override : null;
  const pct = active?.pct ?? plan?.base ?? null;

  // The system suggests funds for the risk level (steadier at low risk, higher-growth at high risk) and
  // individual stocks screened from the S&P 500. The client can remove or add any of them.
  const stocks = useStocks(profile.risk);
  const suggested: Record<string, string> = {
    ...plan?.picks,
    ...Object.fromEntries((stocks?.picks ?? []).map((s) => [s.ticker, s.reason])),
  };
  const own = chosen && chosen.risk === profile.risk ? chosen : null;
  const picks: Record<string, Pick> = {};
  for (const g of Object.keys(catalog.products) as ProductGroup[]) {
    if (own?.groups.includes(g)) {
      Object.entries(own.items)
        .filter(([t]) => groupOf(catalog, t) === g)
        .forEach(([t, pick]) => (picks[t] = pick));
    } else {
      Object.entries(suggested)
        .filter(([t]) => groupOf(catalog, t) === g)
        .forEach(([t, reason]) => (picks[t] = { reason, by: "risk" }));
    }
  }

  const next = () => setStep((s) => Math.min(s + 1, steps.length - 1));
  const confirm = (keys: (keyof Profile)[]) => setConfirmed((c) => [...new Set([...c, ...keys])]);

  const applyProfile = (updates: Partial<Profile>) => {
    setProfile((p) => ({ ...p, ...updates }));
    confirm(Object.keys(updates) as (keyof Profile)[]);
  };

  // The server re-validates against the guardrails before the proposal is shown.
  const applyAllocation = async (after: Pct, reason: string) => {
    if (!(await api.validateAllocation(profile, after).catch(() => false))) return false;
    setOverride({ pct: after, key: profileKey, reason });
    setStep(2);
    return true;
  };

  // Add or remove a fund. The first change in a group keeps the system's suggestions for it, minus or plus this one.
  const togglePick = (ticker: string) => {
    const group = groupOf(catalog, ticker);
    if (!group) return;
    setChosen((prev) => {
      const cur = prev && prev.risk === profile.risk ? prev : { risk: profile.risk, groups: [], items: {} };
      const items = { ...cur.items };
      if (!cur.groups.includes(group))
        Object.entries(picks)
          .filter(([t]) => groupOf(catalog, t) === group)
          .forEach(([t, pick]) => (items[t] = pick));
      if (items[ticker]) delete items[ticker];
      else items[ticker] = { reason: "Added by you.", by: "you" };
      return { risk: profile.risk, groups: [...new Set([...cur.groups, group])], items };
    });
  };

  const applyProducts = (group: ProductGroup, tickers: string[], reason: string) => {
    setChosen((prev) => {
      const cur = prev && prev.risk === profile.risk ? prev : { risk: profile.risk, groups: [], items: {} };
      const kept = Object.fromEntries(Object.entries(cur.items).filter(([t]) => groupOf(catalog, t) !== group));
      const added = Object.fromEntries(tickers.map((t) => [t, { reason, by: "advisor" as const }]));
      return { risk: profile.risk, groups: [...new Set([...cur.groups, group])], items: { ...kept, ...added } };
    });
    setStep(2);
    return true;
  };

  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <aside className="border-b border-slate-200 bg-slate-50 md:w-64 md:shrink-0 md:border-b-0 md:border-r">
        <div className="px-5 py-4 md:py-6">
          <p className="font-semibold text-slate-900">WealthPilot AI</p>
          <p className="text-xs text-slate-500">Your money, smarter future</p>
        </div>
        <nav className="flex gap-1 overflow-x-auto px-3 pb-3 md:flex-col md:pb-0">
          {steps.map((label, i) => (
            <button
              key={label}
              onClick={() => setStep(i)}
              aria-current={i === step ? "step" : undefined}
              className={`flex shrink-0 items-center gap-3 rounded-lg px-3 py-2 text-left text-sm ${
                i === step ? "bg-blue-600 font-medium text-white" : "text-slate-700 hover:bg-slate-200"
              }`}
            >
              <span
                className={`flex h-6 w-6 items-center justify-center rounded-full text-xs ${
                  i === step ? "bg-white/20" : "bg-slate-200"
                }`}
              >
                {i + 1}
              </span>
              <span className="whitespace-nowrap">{label}</span>
            </button>
          ))}
        </nav>
      </aside>

      <main className="flex-1 px-5 py-8 md:px-12 md:py-10">
        {step === 0 && <InfoStep profile={profile} setProfile={setProfile} confirm={confirm} onNext={next} />}
        {step === 1 && (plan ? <AnalysisStep profile={profile} analysis={plan.analysis} onNext={next} /> : <Loading />)}
        {step === 2 &&
          (plan && pct ? (
            <PlanPage
              profile={profile}
              onProfile={applyProfile}
              pct={pct}
              base={plan.base}
              stale={stale}
              adjusted={active?.reason ?? null}
              onReset={() => setOverride(null)}
              picks={picks}
              market={market}
              onClearPicks={own ? () => setChosen(null) : null}
              stocks={stocks}
              onTogglePick={togglePick}
              onWhy={() => {
                setAdvisorOpen(true);
                advisor.current?.ask("Why did you choose this allocation for me?");
              }}
            />
          ) : (
            <Loading />
          ))}
      </main>

      {!advisorOpen && (
        <button
          onClick={() => setAdvisorOpen(true)}
          className="fixed bottom-5 right-5 z-10 rounded-full bg-blue-600 px-5 py-3 text-sm font-medium text-white shadow-lg hover:bg-blue-700"
        >
          Ask the advisor
        </button>
      )}
      <Advisor
        ref={advisor}
        open={advisorOpen}
        onClose={() => setAdvisorOpen(false)}
        profile={profile}
        confirmed={confirmed}
        pct={pct}
        picks={Object.keys(picks)}
        onProfile={applyProfile}
        onApplyAllocation={applyAllocation}
        onApplyProducts={applyProducts}
        onGoto={setStep}
      />
    </div>
  );
}
