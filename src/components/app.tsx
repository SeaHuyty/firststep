"use client";

import { useState } from "react";
import { allocatePct, defaultProfile, groupOf, validPct, type Pct, type ProductGroup, type Profile } from "@/lib/plan";
import { Advisor } from "./advisor";
import { AnalysisStep, InfoStep, PlanStep, ProductsStep, WhatIfStep } from "./steps";

const steps = ["Enter Your Information", "AI Analysis", "Personalized Plan", "Product Details", "What-If Simulation"];

export default function App() {
  const [step, setStep] = useState(0);
  const [profile, setProfile] = useState<Profile>(defaultProfile);
  const [confirmed, setConfirmed] = useState<(keyof Profile)[]>([]);
  // Advisor-proposed allocation, valid only for the profile it was made for.
  const [override, setOverride] = useState<{ pct: Pct; key: string; reason: string } | null>(null);
  const [picks, setPicks] = useState<Record<string, string>>({}); // ticker -> advisor's reason
  const [advisorOpen, setAdvisorOpen] = useState(false);

  const next = () => setStep((s) => Math.min(s + 1, steps.length - 1));
  const profileKey = JSON.stringify(profile);
  const base = allocatePct(profile);
  const active = override && override.key === profileKey ? override : null;
  const pct = active ? active.pct : base;

  const confirm = (keys: (keyof Profile)[]) => setConfirmed((c) => [...new Set([...c, ...keys])]);

  const applyProfile = (updates: Partial<Profile>) => {
    setProfile((p) => ({ ...p, ...updates }));
    confirm(Object.keys(updates) as (keyof Profile)[]);
  };

  const applyAllocation = (after: Pct, reason: string) => {
    if (!validPct(profile, after)) return false;
    setOverride({ pct: after, key: profileKey, reason });
    setStep(2);
    return true;
  };

  const applyProducts = (group: ProductGroup, tickers: string[], reason: string) => {
    setPicks((prev) => {
      const kept = Object.fromEntries(Object.entries(prev).filter(([t]) => groupOf(t) !== group));
      return { ...kept, ...Object.fromEntries(tickers.map((t) => [t, reason])) };
    });
    setStep(3);
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
        <p className="hidden px-5 py-6 text-xs leading-relaxed text-slate-400 md:block">
          Educational prototype. Not personalised financial advice.
        </p>
      </aside>

      <main className={`flex-1 px-5 py-8 md:px-12 md:py-10 ${advisorOpen ? "lg:pr-[26rem]" : ""}`}>
        {step === 0 && <InfoStep profile={profile} setProfile={setProfile} confirm={confirm} onNext={next} />}
        {step === 1 && <AnalysisStep profile={profile} onNext={next} />}
        {step === 2 && (
          <PlanStep
            profile={profile}
            pct={pct}
            base={base}
            adjusted={active?.reason ?? null}
            onReset={() => setOverride(null)}
            onNext={next}
          />
        )}
        {step === 3 && (
          <ProductsStep profile={profile} pct={pct} picks={picks} onResetPicks={() => setPicks({})} onNext={next} />
        )}
        {step === 4 && <WhatIfStep profile={profile} />}
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
