"use client";

import type { ReactNode } from "react";
import { useCatalog } from "@/lib/catalog";
import type { Analysis, Goal, Horizon, Profile, Risk, Status } from "@/lib/types";

export const inputCls =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100";

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium text-slate-700">{label}</span>
      {children}
    </label>
  );
}

export function Title({ title, sub }: { title: string; sub: string }) {
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

export function Loading() {
  return <p className="text-sm text-slate-500">Loading…</p>;
}

export function Select({
  value,
  options,
  onChange,
}: {
  value: string | number;
  options: Record<string, string>;
  onChange: (v: string) => void;
}) {
  return (
    <select className={inputCls} value={value} onChange={(e) => onChange(e.target.value)}>
      {Object.entries(options).map(([k, label]) => (
        <option key={k} value={k}>
          {label}
        </option>
      ))}
    </select>
  );
}

/* 1 — Enter information */
const FIELD_KEYS: (keyof Profile)[] = ["amount", "goal", "horizon", "emergency", "risk", "debt"];

export function InfoStep({
  profile,
  setProfile,
  confirm,
  onNext,
}: {
  profile: Profile;
  setProfile: (p: Profile) => void;
  confirm: (keys: (keyof Profile)[]) => void;
  onNext: () => void;
}) {
  const { labels } = useCatalog();
  const set = <K extends keyof Profile>(k: K, v: Profile[K]) => {
    setProfile({ ...profile, [k]: v });
    confirm([k]);
  };
  return (
    <div className="max-w-lg">
      <Title title="Let’s get to know you" sub="Tell us about your finances and goals, or just chat with the advisor." />
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
            {(Object.keys(labels.goal) as Goal[]).map((g) => (
              <button
                key={g}
                onClick={() => set("goal", g)}
                className={`rounded-lg border px-3 py-2 text-sm ${
                  profile.goal === g
                    ? "border-blue-600 bg-blue-50 font-medium text-blue-700"
                    : "border-slate-300 text-slate-700 hover:bg-slate-50"
                }`}
              >
                {labels.goal[g]}
              </button>
            ))}
          </div>
        </div>

        <Field label="When will you need the money?">
          <Select value={profile.horizon} options={labels.horizon} onChange={(v) => set("horizon", Number(v) as Horizon)} />
        </Field>
        <Field label="Emergency savings">
          <Select value={profile.emergency} options={labels.emergency} onChange={(v) => set("emergency", v as Profile["emergency"])} />
        </Field>
        <Field label="Outstanding debt">
          <Select value={profile.debt} options={labels.debt} onChange={(v) => set("debt", v as Profile["debt"])} />
        </Field>

        <Field label={`Risk tolerance: ${labels.risk[profile.risk]}`}>
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
      <Next
        onClick={() => {
          confirm(FIELD_KEYS);
          onNext();
        }}
      >
        Analyse my situation →
      </Next>
    </div>
  );
}

/* 2 — AI analysis */
const statusCls: Record<Status, string> = {
  good: "text-emerald-600",
  ok: "text-amber-600",
  bad: "text-rose-600",
};

const riskBlurb: Record<Risk, string> = {
  1: "You prefer stability over higher returns.",
  2: "You can accept some market swings for higher returns.",
  3: "You accept large swings in pursuit of growth.",
};

export function AnalysisStep({ profile, analysis, onNext }: { profile: Profile; analysis: Analysis; onNext: () => void }) {
  const { labels } = useCatalog();
  const { score, rows, insights } = analysis;
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
        <p className="mt-1 text-2xl font-semibold text-blue-600">{labels.risk[profile.risk]}</p>
        <p className="text-sm text-slate-500">{riskBlurb[profile.risk]}</p>
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
