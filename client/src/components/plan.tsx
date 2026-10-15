"use client";

import { useEffect, useState, type ReactNode } from "react";
import { api } from "@/lib/api";
import { useCatalog } from "@/lib/catalog";
import {
  BUCKETS,
  BUCKET_COLORS,
  groupOf,
  slicesFromPct,
  usd,
  type MarketItem,
  type Market,
  type Pct,
  type Product,
  type ProductGroup,
  type Profile,
  type Risk,
  type Stocks,
  type WhatIf,
} from "@/lib/types";
import { Donut, LineChart } from "./charts";
import { Field, Select, Title, inputCls } from "./steps";

// One page for allocation, products and the what-if: they all hang off the same two levers
// (amount and risk level), so changing either one updates every section together.

export type Pick = { reason: string; by: "advisor" | "risk" | "you" };

const signed = (v: number) => `${v > 0 ? "+" : ""}${v.toFixed(1)}%`;

function Section({ title, sub, children }: { title: string; sub?: string; children: ReactNode }) {
  return (
    <section className="mt-8 border-t border-slate-200 pt-6">
      <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
      {sub && <p className="mt-0.5 text-sm text-slate-500">{sub}</p>}
      <div className="mt-4">{children}</div>
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
  stocks,
  onTogglePick,
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
  stocks: Stocks | null;
  onTogglePick: (ticker: string) => void;
  onWhy: () => void;
}) {
  const { labels } = useCatalog();
  return (
    <div className={`max-w-5xl transition-opacity ${stale ? "opacity-60" : ""}`}>
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
        <Products profile={profile} pct={pct} picks={picks} market={market} onClearPicks={onClearPicks} stocks={stocks} onTogglePick={onTogglePick} />
      </Section>
      <Section title="What if?" sub="See how this exact mix could grow, and change the contribution or time horizon.">
        <Simulation profile={profile} pct={pct} picks={Object.keys(picks)} />
      </Section>
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
      <div className="flex flex-col items-center gap-5 sm:flex-row">
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
        className="mt-5 rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
      >
        Why this allocation?
      </button>
    </>
  );
}

/* Products */
// Issuer logo (Google's favicon service) for funds, a ticker logo for stocks, or a ticker monogram when
// there is none or it fails to load.
function Logo({ ticker, domain, stock }: { ticker: string; domain: string | null; stock: boolean }) {
  const [failed, setFailed] = useState(false);
  const src = domain
    ? `https://www.google.com/s2/favicons?domain=${domain}&sz=64`
    : stock
      ? `https://assets.parqet.com/logos/symbol/${encodeURIComponent(ticker)}?format=png`
      : null;
  if (src && !failed)
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={src}
        alt=""
        width={32}
        height={32}
        className="h-8 w-8 shrink-0 rounded-md border border-slate-200 bg-white p-1"
        onError={() => setFailed(true)}
      />
    );
  return (
    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-slate-100 text-[10px] font-semibold text-slate-500">
      {ticker.slice(0, 3)}
    </span>
  );
}

const pctText = (v: number | undefined, withSign = false) =>
  v === undefined ? "–" : `${withSign && v > 0 ? "+" : ""}${v.toFixed(1)}%`;
const retCls = (v: number | undefined) => (v === undefined ? "text-slate-400" : v >= 0 ? "text-emerald-700" : "text-rose-600");

// A table row: a catalog product, or a stock from the screen.
type Row = Product & { metrics?: MarketItem; stock: boolean };

function Products({
  profile,
  pct,
  picks,
  market,
  onClearPicks,
  stocks,
  onTogglePick,
}: {
  profile: Profile;
  pct: Pct;
  picks: Record<string, Pick>;
  market: Market | null;
  onClearPicks: (() => void) | null;
  stocks: Stocks | null;
  onTogglePick: (ticker: string) => void;
}) {
  const catalog = useCatalog();
  const { products, group_buckets, stock_universe, satellite } = catalog;
  const groups = Object.keys(products) as ProductGroup[];
  const [tab, setTab] = useState<ProductGroup>(groups[0]);
  const individual = tab === "Individual Stocks";

  const slices = slicesFromPct(profile.amount, pct);
  const bucketAmount = (b: string) => slices.find((s) => s.bucket === b)?.amount ?? 0;

  // Display arithmetic only (the what-if applies the same rules on the server): individual stocks share at
  // most `satellite` of the stocks bucket, ETF picks share the rest, and every other bucket is split equally.
  const inGroup = (g: ProductGroup) => Object.keys(picks).filter((t) => groupOf(catalog, t) === g);
  const singles = inGroup("Individual Stocks");
  const etfs = inGroup("Global Stocks (ETF)").filter((t) => t !== "VNQ");
  const dollars = (t: string): number => {
    const g = groupOf(catalog, t);
    if (!g) return 0;
    if (t === "VNQ") return bucketAmount("alt");
    if (g === "Individual Stocks") return (bucketAmount("stocks") * satellite) / singles.length;
    if (g === "Global Stocks (ETF)")
      return (bucketAmount("stocks") * (singles.length ? 1 - satellite : 1)) / Math.max(etfs.length, 1);
    return group_buckets[g].reduce((n, b) => n + bucketAmount(b), 0) / inGroup(g).length;
  };

  const stockRow = (name: string, ticker: string, sector: string, risk: number, metrics?: MarketItem, reason?: string): Row => ({
    name,
    ticker,
    risk,
    fee: "None",
    min: "~$1",
    region: sector,
    blurb: reason ?? "",
    live: true,
    domain: null,
    metrics,
    stock: true,
  });
  const shortlist = (stocks?.picks ?? []).map((s) => stockRow(s.name, s.ticker, s.sector, s.risk, s.metrics, s.reason));
  const extra = Object.keys(picks)
    .filter((t) => groupOf(catalog, t) === "Individual Stocks" && !shortlist.some((r) => r.ticker === t))
    .map((t) => stockRow(stock_universe[t].name, t, stock_universe[t].sector, 4));
  const all: Row[] = individual ? [...extra, ...shortlist] : products[tab].map((p) => ({ ...p, stock: false }));
  const picked = all.filter((p) => picks[p.ticker]);
  const list = [...picked, ...all.filter((p) => !picks[p.ticker])];

  const amount = picked.reduce((n, p) => n + dollars(p.ticker), 0);
  const share = Math.round((amount / Math.max(profile.amount, 1)) * 100);
  const loadingStocks = individual && !shortlist.length && !extra.length;
  return (
    <>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
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
        <div className="flex items-center gap-4">
          {onClearPicks && (
            <button onClick={onClearPicks} className="text-sm text-blue-700 underline hover:no-underline">
              Clear custom picks
            </button>
          )}
        </div>
      </div>

      {individual ? (
        <div className="mb-3 text-sm text-slate-600">
          <p>
            Suggested by the system from a screen of the S&amp;P 500 (about 500 companies) on live price history, with at
            most two per sector.{" "}
            {picked.length > 0 ? (
              <>
                They get <strong className="text-slate-900">{usd(Math.round(amount))}</strong> ({share}% of the plan), at most{" "}
                {Math.round(satellite * 100)}% of your stock slice, split equally. The rest stays in funds. Remove any you
                don’t want.
              </>
            ) : (
              <>Add stocks to put up to {Math.round(satellite * 100)}% of your stock slice into them.</>
            )}
          </p>
          <p className="mt-1 text-xs text-amber-700">
            A single company can lose most of its value. Stock ETFs spread that risk; individual stocks don’t. The screen looks
            only at past prices.
          </p>
        </div>
      ) : (
        <p className="mb-3 text-sm text-slate-600">
          Your plan puts <strong className="text-slate-900">{usd(Math.round(amount))}</strong> ({share}%) in your picks here.
          {picked.length > 0 && " Each bucket is split equally across its picks."}
        </p>
      )}

      {loadingStocks ? (
        <p className="rounded-xl border border-slate-200 p-6 text-sm text-slate-500">
          Screening the S&amp;P 500 for your risk level… the first time takes about a minute.
        </p>
      ) : (
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
                <th className="px-3 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {list.map((p) => {
                const m = p.metrics ?? market?.items[p.ticker];
                const pick = picks[p.ticker];
                return (
                  <tr key={p.ticker} className={`align-top ${pick ? "bg-blue-50/50" : ""}`}>
                    <td className="px-4 py-3">
                      <div className="flex gap-3">
                        <Logo ticker={p.ticker} domain={p.domain} stock={p.stock} />
                        <div className="min-w-0">
                          <div className="font-medium text-slate-900">
                            {p.name}
                            {pick && (
                              <span className="ml-2 whitespace-nowrap rounded-full bg-blue-600 px-2 py-0.5 text-[10px] font-medium text-white">
                                {pick.by === "advisor" ? "Advisor pick" : pick.by === "you" ? "Your pick" : "Fits your risk"}
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-slate-500">
                            {p.ticker} · {p.region}
                            {m?.price !== undefined && <> · ${m.price.toLocaleString("en-US", { minimumFractionDigits: 2 })}</>}
                          </p>
                          {p.blurb && <p className="mt-0.5 text-xs text-slate-500">{p.blurb}</p>}
                          {pick && !p.stock && <p className="mt-1 text-xs italic text-blue-800">{pick.reason}</p>}
                        </div>
                      </div>
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
                        {pick ? usd(Math.round(dollars(p.ticker))) : "–"}
                      </td>
                    )}
                    <td className="px-3 py-3">
                      <button
                        onClick={() => onTogglePick(p.ticker)}
                        className={`whitespace-nowrap rounded-md px-3 py-1.5 text-xs font-medium ${
                          pick ? "text-slate-600 hover:bg-slate-100" : "bg-blue-600 text-white hover:bg-blue-700"
                        }`}
                      >
                        {pick ? "Remove" : "Add"}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
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

      <div className="mt-4 inline-flex rounded-lg bg-slate-100 p-1 text-sm">
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
          <h3 className="mb-2 mt-5 font-medium text-slate-900">Projected portfolio value</h3>
          <LineChart series={d.series} baseline={d.series[0].map((_, i) => profile.amount + result.monthly * 12 * i)} />
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600">
            <span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-emerald-500" />{names[2]} {usd(ends[2])}</span>
            <span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-blue-500" />{names[1]} {usd(ends[1])}</span>
            <span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-red-500" />{names[0]} {usd(ends[0])}</span>
            <span><i className="mr-1 inline-block h-0.5 w-3 bg-slate-400 align-middle" />You put in {usd(d.contributed)}</span>
          </div>

          {isHistory && d.stats && (
            <div className="mt-5">
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

          <p className="mt-5 rounded-lg bg-slate-50 p-3 text-sm leading-relaxed text-slate-600">
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
