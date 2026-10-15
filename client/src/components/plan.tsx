"use client";

import { useEffect, useState, type ReactNode } from "react";
import { api } from "@/lib/api";
import { useCatalog } from "@/lib/catalog";
import {
  BUCKETS,
  BUCKET_COLORS,
  slicesFromPct,
  usd,
  type Market,
  type Pct,
  type ProductGroup,
  type Profile,
  type Risk,
  type WhatIf,
} from "@/lib/types";
import { Donut, LineChart } from "./charts";
import { Field, Select, Title, inputCls } from "./steps";

// One page for allocation, products and the what-if: they all hang off the same two levers
// (amount and risk level), so changing either one updates every section together.

export type Pick = { reason: string; by: "advisor" | "risk" };

const signed = (v: number) => `${v > 0 ? "+" : ""}${v.toFixed(1)}%`;

function Section({ title, sub, children }: { title: string; sub?: string; children: ReactNode }) {
  return (
    <section className="mt-10 border-t border-slate-200 pt-8">
      <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
      {sub && <p className="mt-1 text-sm text-slate-500">{sub}</p>}
      <div className="mt-5">{children}</div>
    </section>
  );
}

export function PlanPage({
  profile,
  onProfile,
  pct,
  base,
  stale,
  adjusted,
  onReset,
  picks,
  market,
  onClearPicks,
  onWhy,
}: {
  profile: Profile;
  onProfile: (updates: Partial<Profile>) => void;
  pct: Pct;
  base: Pct;
  stale: boolean; // the numbers shown are from the previous inputs while the new ones load
  adjusted: string | null;
  onReset: () => void;
  picks: Record<string, Pick>;
  market: Market | null;
  onClearPicks: (() => void) | null;
  onWhy: () => void;
}) {
  const { labels } = useCatalog();
  return (
    <div className={`max-w-3xl transition-opacity ${stale ? "opacity-60" : ""}`}>
      <Title
        title="Your plan"
        sub={`Based on your goal (${labels.goal[profile.goal].toLowerCase()}) and situation. Change the amount or risk level and everything below follows.`}
      />
      <div className="grid gap-5 sm:max-w-md sm:grid-cols-2">
        <Field label="Amount to invest">
          <input
            type="number"
            min={0}
            step={100}
            className={inputCls}
            value={profile.amount || ""}
            onChange={(e) => onProfile({ amount: Math.max(0, Number(e.target.value)) })}
          />
        </Field>
        <Field label="Risk level">
          <Select value={profile.risk} options={labels.risk} onChange={(v) => onProfile({ risk: Number(v) as Risk })} />
        </Field>
      </div>

      <Section title="Allocation">
        <Allocation profile={profile} pct={pct} base={base} adjusted={adjusted} onReset={onReset} onWhy={onWhy} />
      </Section>
      <Section
        title="Products"
        sub={`Funds that fit your ${labels.risk[profile.risk].toLowerCase()} risk level, with live market data where available.`}
      >
        <Products profile={profile} pct={pct} picks={picks} market={market} onClearPicks={onClearPicks} />
      </Section>
      <Section title="What if?" sub="See how this exact mix could grow, and change the contribution or time horizon.">
        <Simulation profile={profile} pct={pct} picks={Object.keys(picks)} />
      </Section>
      <p className="mt-10 text-xs text-slate-400">Illustrative, not financial advice.</p>
    </div>
  );
}

/* Allocation */
function Allocation({
  profile,
  pct,
  base,
  adjusted,
  onReset,
  onWhy,
}: {
  profile: Profile;
  pct: Pct;
  base: Pct;
  adjusted: string | null;
  onReset: () => void;
  onWhy: () => void;
}) {
  const { buckets } = useCatalog();
  const slices = slicesFromPct(profile.amount, pct);
  const rows = BUCKETS.filter((b) => pct[b] > 0 || (adjusted && base[b] > 0));
  return (
    <>
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
      <button
        onClick={onWhy}
        className="mt-6 rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
      >
        Why this allocation?
      </button>
    </>
  );
}

/* Products */
const pctText = (v: number | undefined, withSign = false) =>
  v === undefined ? "–" : `${withSign && v > 0 ? "+" : ""}${v.toFixed(1)}%`;
const retCls = (v: number | undefined) => (v === undefined ? "text-slate-400" : v >= 0 ? "text-emerald-700" : "text-rose-600");

function Products({
  profile,
  pct,
  picks,
  market,
  onClearPicks,
}: {
  profile: Profile;
  pct: Pct;
  picks: Record<string, Pick>;
  market: Market | null;
  onClearPicks: (() => void) | null;
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
    <>
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
        {onClearPicks && (
          <button onClick={onClearPicks} className="text-sm text-blue-700 underline hover:no-underline">
            Clear advisor picks
          </button>
        )}
      </div>
      <p className="mb-3 text-sm text-slate-600">
        Your plan puts <strong className="text-slate-900">{usd(amount)}</strong> ({share}%) here.
        {picked.length > 0 && (
          <>
            {" "}
            {picked.length > 1 ? `Split across the ${picked.length} picks, about ${usd(each)} each.` : "All of it goes to the pick."}
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
              const pick = picks[p.ticker];
              return (
                <tr key={p.ticker} className={`align-top ${pick ? "bg-blue-50/50" : ""}`}>
                  <td className="px-4 py-3">
                    <div className="font-medium text-slate-900">
                      {p.name}
                      {pick && (
                        <span className="ml-2 whitespace-nowrap rounded-full bg-blue-600 px-2 py-0.5 text-[10px] font-medium text-white">
                          {pick.by === "advisor" ? "Advisor pick" : "Fits your risk"}
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-slate-500">
                      {p.ticker} · {p.region}
                      {m?.price !== undefined && <> · ${m.price.toLocaleString("en-US", { minimumFractionDigits: 2 })}</>}
                    </p>
                    <p className="mt-0.5 text-xs text-slate-500">{p.blurb}</p>
                    {pick && <p className="mt-1 text-xs italic text-blue-800">{pick.reason}</p>}
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
                    <td className="whitespace-nowrap px-3 py-3 font-medium text-slate-900">{pick ? usd(each) : "–"}</td>
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
    </>
  );
}

/* What-if */
const horizons = [1, 3, 5, 10, 20];

type Basis = "history" | "assumed";
// The result carries its own inputs so the summary never mixes new inputs with an old series.
type WhatIfResult = { monthly: number; years: number; data: WhatIf };

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-200 p-3">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-0.5 text-sm font-semibold text-slate-900">{value}</p>
    </div>
  );
}

function Simulation({ profile, pct, picks }: { profile: Profile; pct: Pct; picks: string[] }) {
  const [monthly, setMonthly] = useState(100);
  const [years, setYears] = useState(10);
  const [basis, setBasis] = useState<Basis>("history");
  const [result, setResult] = useState<WhatIfResult | null>(null);
  const [failed, setFailed] = useState(false);

  const picksKey = picks.join(",");
  useEffect(() => {
    const ctrl = new AbortController();
    const timer = setTimeout(() => {
      api
        .whatIf(
          { profile, pct, picks: picksKey ? picksKey.split(",") : [], monthly, years, risk: profile.risk, basis },
          ctrl.signal,
        )
        .then((data) => {
          setFailed(false);
          setResult({ monthly, years, data });
        })
        .catch(() => {
          if (!ctrl.signal.aborted) setFailed(true);
        });
    }, 150);
    return () => {
      clearTimeout(timer);
      ctrl.abort();
    };
  }, [profile, pct, picksKey, monthly, years, basis]);

  const d = result?.data;
  const isHistory = d?.basis === "history";
  const ends = d?.series.map((s) => s[s.length - 1]);
  const names = isHistory ? ["Weak", "Typical", "Strong"] : ["Pessimistic", "Base", "Optimistic"];

  // Per-fund share of the tested mix, merged across buckets (e.g. cash + emergency fund both use SGOV).
  const mix = new Map<string, number>();
  d?.composition.forEach((c) => c.tickers.forEach((t) => mix.set(t, (mix.get(t) ?? 0) + c.pct / c.tickers.length)));

  return (
    <>
      <div className="grid gap-5 sm:grid-cols-2">
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
      </div>

      <div className="mt-5 inline-flex rounded-lg bg-slate-100 p-1 text-sm">
        {(["history", "assumed"] as const).map((b) => (
          <button
            key={b}
            onClick={() => setBasis(b)}
            className={`rounded-md px-3 py-1.5 ${basis === b ? "bg-white font-medium shadow-sm" : "text-slate-600"}`}
          >
            {b === "history" ? "Live history" : "Standard assumptions"}
          </button>
        ))}
      </div>

      {failed && <p className="mt-6 text-sm text-rose-600">Couldn’t load the projection. Is the server running?</p>}
      {d && ends && result && (
        <>
          {d.fallback_reason && <p className="mt-4 text-sm text-amber-700">{d.fallback_reason}</p>}
          <h3 className="mb-2 mt-6 font-medium text-slate-900">Projected portfolio value</h3>
          <LineChart series={d.series} baseline={d.series[0].map((_, i) => profile.amount + result.monthly * 12 * i)} />
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600">
            <span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-emerald-500" />{names[2]} {usd(ends[2])}</span>
            <span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-blue-500" />{names[1]} {usd(ends[1])}</span>
            <span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-red-500" />{names[0]} {usd(ends[0])}</span>
            <span><i className="mr-1 inline-block h-0.5 w-3 bg-slate-400 align-middle" />You put in {usd(d.contributed)}</span>
          </div>

          {isHistory && d.stats && (
            <div className="mt-6">
              <h3 className="font-medium text-slate-900">How this mix behaved</h3>
              <p className="mt-1 text-xs text-slate-500">
                {[...mix.entries()]
                  .sort((a, b) => b[1] - a[1])
                  .map(([t, w]) => `${Math.round(w)}% ${t}`)
                  .join(" · ")}
                {" "}— real monthly returns, {d.stats.window.start} to {d.stats.window.end} ({d.stats.window.months} months).
              </p>
              <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
                <Stat label="Return per year" value={signed(d.stats.annual_return_pct)} />
                <Stat label="Volatility" value={`${d.stats.volatility_pct.toFixed(1)}%`} />
                <Stat label="Worst drop" value={signed(d.stats.max_drawdown_pct)} />
                <Stat label="Worst 12 months" value={d.stats.worst_12m_pct === null ? "–" : signed(d.stats.worst_12m_pct)} />
              </div>
            </div>
          )}

          <p className="mt-6 rounded-lg bg-slate-50 p-4 text-sm leading-relaxed text-slate-600">
            <strong className="text-slate-900">Key takeaway:</strong>{" "}
            {isHistory ? (
              <>
                we replayed this mix’s real monthly returns in 3,000 simulated futures. With {usd(result.monthly)} a
                month, you’d typically reach about {usd(ends[1])} in {result.years} {result.years === 1 ? "year" : "years"}
                , from {usd(ends[0])} in a weak run to {usd(ends[2])} in a strong one (the 10th to 90th percentile).
                {d.loss_chance_pct !== null && d.loss_chance_pct > 0 && <> In about {d.loss_chance_pct}% of runs you’d end up with less than you put in.</>}{" "}
                The recent past may be kinder or harsher than the future.
              </>
            ) : (
              <>
                with {usd(result.monthly)} a month, your portfolio could grow to around {usd(ends[1])} in {result.years}{" "}
                {result.years === 1 ? "year" : "years"} (base case), using fixed return assumptions for this risk level.
              </>
            )}
          </p>
        </>
      )}
      {!d && !failed && <p className="mt-8 text-sm text-slate-500">Loading…</p>}
    </>
  );
}
