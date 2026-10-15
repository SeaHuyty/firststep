"use client";

import { useState, type ReactNode } from "react";
import { Chat } from "./chat";
import { Donut, LineChart } from "./charts";
import { Explanation } from "./explanation";
import {
  allocate,
  analyse,
  bucketMeta,
  debtLabels,
  emergencyLabels,
  groupBuckets,
  goalLabels,
  horizonLabels,
  products,
  project,
  riskLabels,
  usd,
  type Debt,
  type Emergency,
  type Goal,
  type Horizon,
  type Profile,
  type ProductGroup,
  type Risk,
  type Status,
} from "@/lib/plan";

type StepProps = { profile: Profile; onNext: () => void };

const inputCls =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100";

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium text-slate-700">{label}</span>
      {children}
    </label>
  );
}

function Title({ title, sub }: { title: string; sub: string }) {
  return (
    <header className="mb-6">
      <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{title}</h1>
      <p className="mt-1 text-sm text-slate-500">{sub}</p>
    </header>
  );
}

function Next({ onClick, children }: { onClick: () => void; children: ReactNode }) {
  return (
    <button
      onClick={onClick}
      className="mt-8 rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-700"
    >
      {children}
    </button>
  );
}

function Select<T extends string | number>({
  value,
  options,
  onChange,
}: {
  value: T;
  options: Record<T, string>;
  onChange: (v: T) => void;
}) {
  return (
    <select
      className={inputCls}
      value={value}
      onChange={(e) => {
        const raw = e.target.value;
        onChange((typeof value === "number" ? Number(raw) : raw) as T);
      }}
    >
      {Object.entries<string>(options).map(([k, label]) => (
        <option key={k} value={k}>
          {label}
        </option>
      ))}
    </select>
  );
}

/* 1 — Enter information */
export function InfoStep({
  profile,
  setProfile,
  onNext,
}: StepProps & { setProfile: (p: Profile) => void }) {
  const [mode, setMode] = useState<"form" | "chat">("form");
  const set = <K extends keyof Profile>(k: K, v: Profile[K]) => setProfile({ ...profile, [k]: v });
  return (
    <div className="max-w-lg">
      <Title title="Let’s get to know you" sub="Tell us about your finances and goals so we can build your plan." />
      <div className="mb-6 inline-flex rounded-lg bg-slate-100 p-1 text-sm">
        {(["form", "chat"] as const).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={`rounded-md px-3 py-1.5 ${mode === m ? "bg-white font-medium shadow-sm" : "text-slate-600"}`}
          >
            {m === "form" ? "Fill a form" : "Chat with advisor"}
          </button>
        ))}
      </div>
      <div className={mode === "chat" ? "" : "hidden"}>
        <Chat profile={profile} setProfile={setProfile} onNext={onNext} />
      </div>
      {mode === "form" && (
      <>
      <div className="space-y-5">
        <Field label="Available money">
          <input
            type="number"
            min={0}
            step={100}
            className={inputCls}
            value={profile.amount || ""}
            onChange={(e) => set("amount", Math.max(0, Number(e.target.value)))}
          />
        </Field>

        <div>
          <span className="mb-1.5 block text-sm font-medium text-slate-700">Main goal</span>
          <div className="grid grid-cols-2 gap-2">
            {(Object.keys(goalLabels) as Goal[]).map((g) => (
              <button
                key={g}
                onClick={() => set("goal", g)}
                className={`rounded-lg border px-3 py-2 text-sm ${
                  profile.goal === g
                    ? "border-blue-600 bg-blue-50 font-medium text-blue-700"
                    : "border-slate-300 text-slate-700 hover:bg-slate-50"
                }`}
              >
                {goalLabels[g]}
              </button>
            ))}
          </div>
        </div>

        <Field label="When will you need the money?">
          <Select<Horizon> value={profile.horizon} options={horizonLabels} onChange={(v) => set("horizon", v)} />
        </Field>
        <Field label="Emergency savings">
          <Select<Emergency> value={profile.emergency} options={emergencyLabels} onChange={(v) => set("emergency", v)} />
        </Field>
        <Field label="Outstanding debt">
          <Select<Debt> value={profile.debt} options={debtLabels} onChange={(v) => set("debt", v)} />
        </Field>

        <Field label={`Risk tolerance: ${riskLabels[profile.risk]}`}>
          <input
            type="range"
            min={1}
            max={3}
            step={1}
            className="w-full accent-blue-600"
            value={profile.risk}
            onChange={(e) => set("risk", Number(e.target.value) as Risk)}
          />
        </Field>
      </div>
      <Next onClick={onNext}>Analyse my situation →</Next>
      </>
      )}
    </div>
  );
}

/* 2 — AI analysis */
const statusCls: Record<Status, string> = {
  good: "text-emerald-600",
  ok: "text-amber-600",
  bad: "text-rose-600",
};

export function AnalysisStep({ profile, onNext }: StepProps) {
  const { score, rows, insights } = analyse(profile);
  return (
    <div className="max-w-lg">
      <Title title="AI financial analysis" sub="Your financial profile and key insights." />
      <section className="rounded-xl border border-slate-200 p-5">
        <div className="flex items-baseline justify-between">
          <h2 className="font-medium text-slate-900">Financial health</h2>
          <span className="text-2xl font-semibold text-slate-900">
            {score}
            <span className="text-sm font-normal text-slate-500"> / 100</span>
          </span>
        </div>
        <div className="mt-3 h-2 rounded-full bg-slate-100">
          <div className="h-2 rounded-full bg-emerald-500" style={{ width: `${score}%` }} />
        </div>
        <ul className="mt-4 divide-y divide-slate-100 text-sm">
          {rows.map((r) => (
            <li key={r.label} className="flex justify-between py-2">
              <span className="text-slate-600">{r.label}</span>
              <span className={`font-medium ${statusCls[r.status]}`}>{r.value}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="mt-4 rounded-xl border border-slate-200 p-5">
        <h2 className="font-medium text-slate-900">Risk profile</h2>
        <p className="mt-1 text-2xl font-semibold text-blue-600">{riskLabels[profile.risk]}</p>
        <p className="text-sm text-slate-500">
          {
            {
              1: "You prefer stability over higher returns.",
              2: "You can accept some market swings for higher returns.",
              3: "You accept large swings in pursuit of growth.",
            }[profile.risk]
          }
        </p>
      </section>

      <section className="mt-4 rounded-xl border border-slate-200 p-5">
        <h2 className="font-medium text-slate-900">Key insights</h2>
        <ul className="mt-2 list-disc space-y-1.5 pl-5 text-sm text-slate-600">
          {insights.map((i) => (
            <li key={i}>{i}</li>
          ))}
        </ul>
      </section>
      <Next onClick={onNext}>See my plan →</Next>
    </div>
  );
}

/* 3 — Personalized plan */
export function PlanStep({ profile, onNext }: StepProps) {
  const slices = allocate(profile);
  return (
    <div className="max-w-2xl">
      <Title
        title={`Your ${usd(profile.amount)} allocation plan`}
        sub={`Based on your goal (${goalLabels[profile.goal].toLowerCase()}), risk level and situation.`}
      />
      <div className="flex flex-col items-center gap-6 sm:flex-row">
        <Donut slices={slices} total={profile.amount} />
        <ul className="w-full space-y-2 text-sm">
          {slices.map((s) => (
            <li key={s.bucket} className="flex items-center gap-2">
              <span className="h-3 w-3 rounded-sm" style={{ background: bucketMeta[s.bucket].color }} />
              <span className="flex-1 text-slate-700">{bucketMeta[s.bucket].label}</span>
              <span className="font-medium text-slate-900">{usd(s.amount)}</span>
              <span className="w-10 text-right text-slate-500">{s.pct}%</span>
            </li>
          ))}
        </ul>
      </div>

      <Explanation key={JSON.stringify(profile)} profile={profile} />
      <Next onClick={onNext}>View products →</Next>
    </div>
  );
}

/* 4 — Product details */
export function ProductsStep({ profile, onNext }: StepProps) {
  const groups = Object.keys(products) as ProductGroup[];
  const [tab, setTab] = useState<ProductGroup>(groups[0]);
  const slices = allocate(profile).filter((s) => groupBuckets[tab].includes(s.bucket));
  const pct = slices.reduce((n, s) => n + s.pct, 0);
  const amount = slices.reduce((n, s) => n + s.amount, 0);
  const list = products[tab];
  const split = list.length ? Math.round(amount / list.length) : 0;
  return (
    <div className="max-w-2xl">
      <Title title="Recommended products" sub="Example products for your plan. Illustrative only, not real-time data." />
      <div className="mb-4 inline-flex rounded-lg bg-slate-100 p-1 text-sm">
        {groups.map((g) => (
          <button
            key={g}
            onClick={() => setTab(g)}
            className={`rounded-md px-3 py-1.5 ${tab === g ? "bg-white font-medium shadow-sm" : "text-slate-600"}`}
          >
            {g}
          </button>
        ))}
      </div>
      <p className="mb-3 text-sm text-slate-600">
        Your plan puts <strong className="text-slate-900">{usd(amount)}</strong> ({pct}%) here.
        {list.length > 1 && <> Split evenly, about {usd(split)} each.</>}
      </p>
      <div className="overflow-x-auto rounded-xl border border-slate-200">
        <table className="w-full min-w-[480px] text-left text-sm">
          <thead className="bg-slate-50 text-xs text-slate-500">
            <tr>
              <th className="px-4 py-2 font-medium">Product</th>
              <th className="px-4 py-2 font-medium">Risk</th>
              <th className="px-4 py-2 font-medium">Fee</th>
              <th className="px-4 py-2 font-medium">Min.</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {list.map((p) => (
              <tr key={p.ticker} className="align-top">
                <td className="px-4 py-3">
                  <div className="font-medium text-slate-900">
                    {p.name} <span className="text-xs font-normal text-slate-500">{p.ticker}</span>
                  </div>
                  <p className="mt-0.5 text-xs text-slate-500">{p.blurb}</p>
                </td>
                <td className="px-4 py-3">
                  <div className="flex gap-1 pt-1" aria-label={`Risk ${p.risk} of 5`}>
                    {[1, 2, 3, 4, 5].map((n) => (
                      <span key={n} className={`h-2 w-2 rounded-full ${n <= p.risk ? "bg-blue-600" : "bg-slate-200"}`} />
                    ))}
                  </div>
                </td>
                <td className="whitespace-nowrap px-4 py-3 text-slate-700">{p.fee}</td>
                <td className="whitespace-nowrap px-4 py-3 text-slate-700">{p.min}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Next onClick={onNext}>Try a what-if →</Next>
    </div>
  );
}

/* 5 — What-if simulation */
const horizons = [1, 3, 5, 10, 20];

export function WhatIfStep({ profile }: { profile: Profile }) {
  const [monthly, setMonthly] = useState(100);
  const [years, setYears] = useState(10);
  const [risk, setRisk] = useState<Risk>(profile.risk);
  const series = project(profile.amount, monthly, years, risk);
  const [low, base, high] = series.map((s) => s[s.length - 1]);

  return (
    <div className="max-w-2xl">
      <Title title="What-if simulation" sub="Change contribution, time horizon or risk level to see different outcomes." />
      <div className="grid gap-5 sm:grid-cols-3">
        <Field label={`Monthly contribution: ${usd(monthly)}`}>
          <input
            type="range"
            min={0}
            max={500}
            step={25}
            className="w-full accent-blue-600"
            value={monthly}
            onChange={(e) => setMonthly(Number(e.target.value))}
          />
        </Field>
        <Field label="Time horizon">
          <select className={inputCls} value={years} onChange={(e) => setYears(Number(e.target.value))}>
            {horizons.map((y) => (
              <option key={y} value={y}>
                {y} {y === 1 ? "year" : "years"}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Risk level">
          <Select<Risk> value={risk} options={riskLabels} onChange={setRisk} />
        </Field>
      </div>

      <h2 className="mb-2 mt-8 font-medium text-slate-900">Projected portfolio value</h2>
      <LineChart series={series} />
      <div className="mt-2 flex gap-4 text-xs text-slate-600">
        <span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-emerald-500" />Optimistic {usd(high)}</span>
        <span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-blue-500" />Base {usd(base)}</span>
        <span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-red-500" />Pessimistic {usd(low)}</span>
      </div>

      <p className="mt-6 rounded-lg bg-slate-50 p-4 text-sm text-slate-600">
        <strong className="text-slate-900">Key takeaway:</strong> with {usd(monthly)} a month, your portfolio could
        grow to around {usd(base)} in {years} {years === 1 ? "year" : "years"} (base case). Actual returns can be
        higher or lower. Illustrative scenario, not financial advice.
      </p>
    </div>
  );
}
