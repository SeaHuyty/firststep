"use client";

// Charts draw only numbers the server sent. Each has a table alternative.
import { type ReactNode, useEffect, useRef, useState } from "react";
import { DataTable } from "@/components/ui/primitives";
import { FAMILY_LABEL } from "@/lib/copy";
import { money, pct } from "@/lib/format";

const FAMILY_ORDER = ["cash", "bonds", "stocks", "gold"] as const;
const FAMILY_COLOR: Record<string, string> = {
  cash: "var(--color-asset-cash)",
  bonds: "var(--color-asset-bonds)",
  stocks: "var(--color-asset-stocks)",
  gold: "var(--color-asset-gold)",
};

/** Four families, not seven asset classes: a beginner reads the shape, the table has detail. */
export function AllocationDonut({
  families,
  total,
  children,
}: {
  families: Record<string, number>;
  total: string;
  /** A legend of your own beside the donut (e.g. what each part is for); defaults to labels. */
  children?: ReactNode;
}) {
  // Draws in once (600 ms, docs/standards/brand.md section 7); instant with reduced motion.
  const [drawn, setDrawn] = useState(false);
  useEffect(() => {
    const frame = requestAnimationFrame(() => setDrawn(true));
    return () => cancelAnimationFrame(frame);
  }, []);
  const r = 64;
  const c = 2 * Math.PI * r;
  const slices = FAMILY_ORDER.map((f) => ({ family: f, pct: families[f] ?? 0 })).filter((s) => s.pct > 0);
  // Each slice starts where the previous ones end (computed up front, so render stays pure).
  const starts = slices.map((_, i) => slices.slice(0, i).reduce((sum, s) => sum + (s.pct / 100) * c, 0));
  return (
    <div>
      <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-center">
        <svg viewBox="0 0 180 180" className="size-44 shrink-0" role="img" aria-label="Plan by asset family">
          <g transform="rotate(-90 90 90)">
            {slices.map((s, i) => {
              const len = (s.pct / 100) * c;
              return (
                <circle
                  key={s.family}
                  cx="90"
                  cy="90"
                  r={r}
                  fill="none"
                  stroke={FAMILY_COLOR[s.family]}
                  strokeWidth="26"
                  strokeDasharray={drawn ? `${len} ${c - len}` : `0 ${c}`}
                  strokeDashoffset={-(starts[i] ?? 0)}
                  style={{ transition: "stroke-dasharray 600ms var(--ease-standard)" }}
                />
              );
            })}
          </g>
          <text x="90" y="86" textAnchor="middle" className="fill-muted text-[12px]">
            Total
          </text>
          <text x="90" y="104" textAnchor="middle" className="tnum fill-ink text-[17px] font-semibold">
            {money(total)}
          </text>
        </svg>
        {children ?? <ul className="grid w-full grid-cols-2 gap-x-4 gap-y-2">
          {slices.map(({ family: f }) => (
            <li key={f} className="flex items-center gap-2">
              <span aria-hidden className="size-3 rounded-full" style={{ background: FAMILY_COLOR[f] }} />
              <span className="text-body-sm text-ink-2">{FAMILY_LABEL[f]}</span>
              <span className="tnum ml-auto text-label text-ink">{pct(families[f] ?? 0)}</span>
            </li>
          ))}
        </ul>}
      </div>
    </div>
  );
}

export function FamilyDot({ family }: { family: string }) {
  return <span aria-hidden className="mt-1.5 size-3 shrink-0 rounded-full" style={{ background: FAMILY_COLOR[family] }} />;
}

/**
 * Range of outcomes: the p10-p90 band, the p50 line and the money paid in, so the bad case is
 * read against what you put in. Always titled as a range and captioned "not a prediction".
 */
export function ProjectionFan({
  years,
  p10,
  p50,
  p90,
  paidIn,
}: {
  years: number[];
  p10: number[];
  p50: number[];
  p90: number[];
  paidIn: number[];
}) {
  // Drawn at the container's real width (not a scaled viewBox), so axis text stays 12px on a
  // phone as well as on a desktop (docs/standards/ui-spec.md: nothing below 12px).
  const box = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(560);
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => entry && setW(Math.max(280, Math.round(entry.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const h = w < 480 ? 200 : 220;
  const pad = { l: 56, r: 16, t: 12, b: 28 };
  const max = Math.max(...p90, ...paidIn, 1);
  const n = Math.max(years.length - 1, 1);
  const x = (i: number) => pad.l + (i / n) * (w - pad.l - pad.r);
  const y = (v: number) => h - pad.b - (v / max) * (h - pad.t - pad.b);
  const line = (vals: number[]) => vals.map((v, i) => `${i === 0 ? "M" : "L"}${x(i)},${y(v)}`).join(" ");
  const band = `${line(p90)} ${[...p10].reverse().map((v, i) => `L${x(p10.length - 1 - i)},${y(v)}`).join(" ")} Z`;
  const ticks = [0, 0.5, 1].map((f) => Math.round((max * f) / 1000) * 1000);
  const last = years.length - 1;
  return (
    <div ref={box}>
      <svg width={w} height={h} className="block max-w-full" role="img" aria-label="Range of outcomes by year">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={pad.l} x2={w - pad.r} y1={y(t)} y2={y(t)} stroke="var(--color-line)" />
            <text x={pad.l - 8} y={y(t) + 4} textAnchor="end" className="tnum fill-muted text-[12px]">
              {money(t)}
            </text>
          </g>
        ))}
        <path d={band} fill="var(--color-primary)" fillOpacity={0.18} className="animate-fade" />
        <path d={line(paidIn)} fill="none" stroke="var(--color-ink-2)" strokeWidth={1.5} strokeDasharray="4 4" />
        <path d={line(p50)} fill="none" stroke="var(--color-primary)" strokeWidth={2} />
        {years.map((yr, i) =>
          i % Math.max(1, Math.ceil(years.length / 6)) === 0 || i === last ? (
            <text key={yr} x={x(i)} y={h - 8} textAnchor="middle" className="fill-muted text-[12px]">
              {yr === 0 ? "Now" : `${yr}y`}
            </text>
          ) : null,
        )}
      </svg>
      <ul className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-caption text-ink-2">
        <li className="flex items-center gap-2">
          <span aria-hidden className="h-3 w-5 rounded-sm bg-primary/20" /> Bad to good case
        </li>
        <li className="flex items-center gap-2">
          <span aria-hidden className="h-0.5 w-5 bg-primary" /> Typical case
        </li>
        <li className="flex items-center gap-2">
          <span aria-hidden className="h-0 w-5 border-t-2 border-dashed border-ink-2" /> Money you put in
        </li>
      </ul>
      <DataTable
        caption="Range of outcomes by year"
        head={["Year", "Bad case", "Typical", "Good case", "Paid in"]}
        rows={years.map((yr, i) => [
          yr === 0 ? "Now" : `Year ${yr}`,
          money(p10[i] ?? 0),
          money(p50[i] ?? 0),
          money(p90[i] ?? 0),
          money(paidIn[i] ?? 0),
        ])}
      />
    </div>
  );
}
