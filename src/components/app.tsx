"use client";

import { useState } from "react";
import { defaultProfile, type Profile } from "@/lib/plan";
import { AnalysisStep, InfoStep, PlanStep, ProductsStep, WhatIfStep } from "./steps";

const steps = ["Enter Your Information", "AI Analysis", "Personalized Plan", "Product Details", "What-If Simulation"];

export default function App() {
  const [step, setStep] = useState(0);
  const [profile, setProfile] = useState<Profile>(defaultProfile);
  const next = () => setStep((s) => Math.min(s + 1, steps.length - 1));

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

      <main className="flex-1 px-5 py-8 md:px-12 md:py-10">
        {step === 0 && <InfoStep profile={profile} setProfile={setProfile} onNext={next} />}
        {step === 1 && <AnalysisStep profile={profile} onNext={next} />}
        {step === 2 && <PlanStep profile={profile} onNext={next} />}
        {step === 3 && <ProductsStep profile={profile} onNext={next} />}
        {step === 4 && <WhatIfStep profile={profile} />}
      </main>
    </div>
  );
}
