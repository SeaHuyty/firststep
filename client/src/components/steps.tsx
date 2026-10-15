"use client";

import { useEffect, useState, type ReactNode } from "react";
import { api } from "@/lib/api";
import { useCatalog } from "@/lib/catalog";
import {
  BUCKETS,
  BUCKET_COLORS,
  slicesFromPct,
  usd,
  type Analysis,
  type Goal,
  type Horizon,
  type Market,
  type Pct,
  type ProductGroup,
  type Profile,
  type Risk,
  type Status,
} from "@/lib/types";
import { Donut, LineChart } from "./charts";
import { Explanation } from "./explanation";

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

export function Loading() {
  return <p className="text-sm text-slate-500">Loading…</p>;
}

function Select({
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

/* 3 — Personalized plan */
export function PlanStep({
  profile,
  pct,
  base,
  adjusted,
  onReset,
  onNext,
}: {
  profile: Profile;
  pct: Pct;
  base: Pct;
  adjusted: string | null;
  onReset: () => void;
  onNext: () => void;
}) {
  const { labels, buckets } = useCatalog();
  const slices = slicesFromPct(profile.amount, pct);
  const rows = BUCKETS.filter((b) => pct[b] > 0 || (adjusted && base[b] > 0));
  return (
    <div className="max-w-2xl">
      <Title
        title={`Your ${usd(profile.amount)} allocation plan`}
        sub={`Based on your goal (${labels.goal[profile.goal].toLowerCase()}), risk level and situation.`}
      />
      {adjusted && (
        <div className="mb-5 flex items-start justify-between gap-4 rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm text-blue-900">
          <p>
            <strong>Adjusted with your advisor.</strong> {adjusted}
          </p>
          <button onClick={onReset} className="shrink-0 text-blue-700 underline hover:no-underline">
            Reset
          </button>
        </div>
      )}
      <div className="flex flex-col items-center gap-6 sm:flex-row">
        <Donut slices={slices} total={profile.amount} />
        <ul className="w-full space-y-2 text-sm">
          {rows.map((b) => {
            const delta = pct[b] - base[b];
            return (
              <li key={b} className="flex items-center gap-2">
                <span className="h-3 w-3 rounded-sm" style={{ background: BUCKET_COLORS[b] }} />
                <span className="flex-1 text-slate-700">{buckets[b].label}</span>
                {adjusted && delta !== 0 && (
                  <span className={`text-xs font-medium ${delta > 0 ? "text-emerald-600" : "text-amber-600"}`}>
                    {delta > 0 ? "+" : ""}
                    {delta}
                  </span>
                )}
                <span className="font-medium text-slate-900">{usd(Math.round((profile.amount * pct[b]) / 100))}</span>
                <span className="w-10 text-right text-slate-500">{pct[b]}%</span>
              </li>
            );
          })}
        </ul>
      </div>

      <Explanation key={JSON.stringify([profile, pct])} profile={profile} pct={pct} />
      <Next onClick={onNext}>View products →</Next>
    </div>
  );
}

/* 4 — Product details */
const pctText = (v: number | undefined, signed = false) =>
  v === undefined ? "–" : `${signed && v > 0 ? "+" : ""}${v.toFixed(1)}%`;
const retCls = (v: number | undefined) => (v === undefined ? "text-slate-400" : v >= 0 ? "text-emerald-700" : "text-rose-600");

export function ProductsStep({
  profile,
  pct,
  picks,
  market,
  onResetPicks,
  onNext,
}: {
  profile: Profile;
  pct: Pct;
  picks: Record<string, string>;
  market: Market | null;
  onResetPicks: () => void;
  onNext: () => void;
}) {
  const { products, group_buckets } = useCatalog();
  const groups = Object.keys(products) as ProductGroup[];
  const [tab, setTab] = useState<ProductGroup>(groups[0]);
  const slices = slicesFromPct(profile.amount, pct).filter((s) => group_buckets[tab].includes(s.bucket));
  const share = slices.reduce((n, s) => n + s.pct, 0);
  const amount = slices.reduce((n, s) => n + s.amount, 0);
  const all = products[tab];
  const picked = all.filter((p) => picks[p.ticker]);
  const list = [...picked, ...all.filter((p) => !picks[p.ticker])];
  const each = picked.length ? Math.round(amount / picked.length) : 0;
  return (
    <div className="max-w-3xl">
      <Title title="Recommended products" sub="Example products for your plan, with live market data where available." />
      <div className="mb-4 flex items-center justify-between gap-4">
        <div className="inline-flex rounded-lg bg-slate-100 p-1 text-sm">
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
        {Object.keys(picks).length > 0 && (
          <button onClick={onResetPicks} className="text-sm text-blue-700 underline hover:no-underline">
            Clear advisor picks
          </button>
        )}
      </div>
      <p className="mb-3 text-sm text-slate-600">
        Your plan puts <strong className="text-slate-900">{usd(amount)}</strong> ({share}%) here.
        {picked.length > 0 && (
          <>
            {" "}
            {picked.length > 1 ? `Split across your ${picked.length} picks, about ${usd(each)} each.` : "All of it goes to your pick."}
          </>
        )}
      </p>
      <div className="overflow-x-auto rounded-xl border border-slate-200">
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead className="bg-slate-50 text-xs text-slate-500">
            <tr>
              <th className="px-4 py-2 font-medium">Product</th>
              <th className="px-3 py-2 font-medium">Risk</th>
              <th className="px-3 py-2 font-medium">Fee</th>
              <th className="px-3 py-2 font-medium">1Y</th>
              <th className="px-3 py-2 font-medium">5Y/yr</th>
              <th className="px-3 py-2 font-medium">Volatility</th>
              <th className="px-3 py-2 font-medium">Min.</th>
              {picked.length > 0 && <th className="px-3 py-2 font-medium">Your $</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {list.map((p) => {
              const m = market?.items[p.ticker];
              return (
                <tr key={p.ticker} className={`align-top ${picks[p.ticker] ? "bg-blue-50/50" : ""}`}>
                  <td className="px-4 py-3">
                    <div className="font-medium text-slate-900">
                      {p.name}
                      {picks[p.ticker] && (
                        <span className="ml-2 rounded-full bg-blue-600 px-2 py-0.5 text-[10px] font-medium text-white">
                          Advisor pick
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-slate-500">
                      {p.ticker} · {p.region}
                      {m?.price !== undefined && <> · ${m.price.toLocaleString("en-US", { minimumFractionDigits: 2 })}</>}
                    </p>
                    <p className="mt-0.5 text-xs text-slate-500">{p.blurb}</p>
                    {picks[p.ticker] && <p className="mt-1 text-xs italic text-blue-800">{picks[p.ticker]}</p>}
                  </td>
                  <td className="px-3 py-3">
                    <div className="flex gap-1 pt-1" aria-label={`Risk ${p.risk} of 5`}>
                      {[1, 2, 3, 4, 5].map((n) => (
                        <span key={n} className={`h-2 w-2 rounded-full ${n <= p.risk ? "bg-blue-600" : "bg-slate-200"}`} />
                      ))}
                    </div>
                  </td>
                  <td className="whitespace-nowrap px-3 py-3 text-slate-700">
                    {m?.expense_ratio_pct !== undefined ? `${m.expense_ratio_pct}%` : p.fee}
                  </td>
                  <td className={`whitespace-nowrap px-3 py-3 ${retCls(m?.ret_1y_pct)}`}>{pctText(m?.ret_1y_pct, true)}</td>
                  <td className={`whitespace-nowrap px-3 py-3 ${retCls(m?.ret_5y_pct)}`}>{pctText(m?.ret_5y_pct, true)}</td>
                  <td className="whitespace-nowrap px-3 py-3 text-slate-700">{pctText(m?.volatility_pct)}</td>
                  <td className="whitespace-nowrap px-3 py-3 text-slate-700">{p.min}</td>
                  {picked.length > 0 && (
                    <td className="whitespace-nowrap px-3 py-3 font-medium text-slate-900">
                      {picks[p.ticker] ? usd(each) : "–"}
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-xs leading-relaxed text-slate-500">
        {market === null
          ? "Loading live data…"
          : market.asof
            ? `Live data from Yahoo Finance (unofficial, may be delayed), as of ${new Date(market.asof).toLocaleString()}. 1Y is total return, 5Y/yr is annualized, volatility is the annualized spread of daily returns over up to 3 years. Savings accounts and money market funds have no market listing, so no live figures. Past performance does not predict future results.`
            : "Live data is unavailable right now, so fees shown are illustrative and returns are hidden."}
      </p>
      <Next onClick={onNext}>Try a what-if →</Next>
    </div>
  );
}

/* 5 — What-if simulation */
const horizons = [1, 3, 5, 10, 20];

type Projection = { monthly: number; years: number; series: [number[], number[], number[]] };

export function WhatIfStep({ profile }: { profile: Profile }) {
  const { labels } = useCatalog();
  const [monthly, setMonthly] = useState(100);
  const [years, setYears] = useState(10);
  const [risk, setRisk] = useState<Risk>(profile.risk);
  // The result carries its own inputs so the summary never mixes new inputs with an old series.
  const [result, setResult] = useState<Projection | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const ctrl = new AbortController();
    const timer = setTimeout(() => {
      api
        .projection({ amount: profile.amount, monthly, years, risk }, ctrl.signal)
        .then((series) => {
          setFailed(false);
          setResult({ monthly, years, series });
        })
        .catch(() => {
          if (!ctrl.signal.aborted) setFailed(true);
        });
    }, 150);
    return () => {
      clearTimeout(timer);
      ctrl.abort();
    };
  }, [profile.amount, monthly, years, risk]);

  const ends = result?.series.map((s) => s[s.length - 1]);

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
          <Select value={risk} options={labels.risk} onChange={(v) => setRisk(Number(v) as Risk)} />
        </Field>
      </div>

      {failed && <p className="mt-6 text-sm text-rose-600">Couldn’t load the projection. Is the server running?</p>}
      {result && ends && (
        <>
          <h2 className="mb-2 mt-8 font-medium text-slate-900">Projected portfolio value</h2>
          <LineChart series={result.series} />
          <div className="mt-2 flex gap-4 text-xs text-slate-600">
            <span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-emerald-500" />Optimistic {usd(ends[2])}</span>
            <span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-blue-500" />Base {usd(ends[1])}</span>
            <span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-red-500" />Pessimistic {usd(ends[0])}</span>
          </div>

          <p className="mt-6 rounded-lg bg-slate-50 p-4 text-sm text-slate-600">
            <strong className="text-slate-900">Key takeaway:</strong> with {usd(result.monthly)} a month, your portfolio
            could grow to around {usd(ends[1])} in {result.years} {result.years === 1 ? "year" : "years"} (base case).
            Actual returns can be higher or lower. Illustrative scenario, not financial advice.
          </p>
        </>
      )}
      {!result && !failed && <p className="mt-8 text-sm text-slate-500">Loading…</p>}
    </div>
  );
}
