import { bucketMeta, usd, type Slice } from "@/lib/plan";

export function Donut({ slices, total }: { slices: Slice[]; total: number }) {
  const r = 70;
  const c = 2 * Math.PI * r;
  return (
    <svg viewBox="0 0 200 200" className="h-52 w-52 shrink-0" role="img" aria-label="Allocation chart">
      <g transform="rotate(-90 100 100)">
        {slices.map((s, i) => {
          const len = (s.pct / 100) * c;
          const offset = (slices.slice(0, i).reduce((sum, x) => sum + x.pct, 0) / 100) * c;
          return (
            <circle
              key={s.bucket}
              cx="100"
              cy="100"
              r={r}
              fill="none"
              stroke={bucketMeta[s.bucket].color}
              strokeWidth="28"
              strokeDasharray={`${len} ${c - len}`}
              strokeDashoffset={-offset}
            />
          );
        })}
      </g>
      <text x="100" y="98" textAnchor="middle" className="fill-slate-900 text-[18px] font-semibold">
        {usd(total)}
      </text>
      <text x="100" y="116" textAnchor="middle" className="fill-slate-500 text-[11px]">
        Total
      </text>
    </svg>
  );
}

const lineColors = ["#ef4444", "#3b82f6", "#10b981"]; // pessimistic, base, optimistic

export function LineChart({ series }: { series: [number[], number[], number[]] }) {
  const w = 480;
  const h = 220;
  const pad = { l: 48, r: 12, t: 12, b: 24 };
  const years = series[0].length - 1;
  const max = Math.max(...series.flat(), 1);
  const x = (i: number) => pad.l + (i / Math.max(years, 1)) * (w - pad.l - pad.r);
  const y = (v: number) => pad.t + (1 - Math.max(v, 0) / max) * (h - pad.t - pad.b);
  const ticks = [0, 0.5, 1].map((t) => Math.round((max * t) / 100) * 100);

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full" role="img" aria-label="Projected portfolio value">
      {ticks.map((t) => (
        <g key={t}>
          <line x1={pad.l} x2={w - pad.r} y1={y(t)} y2={y(t)} stroke="#e2e8f0" />
          <text x={pad.l - 6} y={y(t) + 4} textAnchor="end" className="fill-slate-500 text-[10px]">
            {usd(t)}
          </text>
        </g>
      ))}
      {[0, years].map((i) => (
        <text key={i} x={x(i)} y={h - 6} textAnchor={i === 0 ? "start" : "end"} className="fill-slate-500 text-[10px]">
          {i === 0 ? "Now" : `${i} yrs`}
        </text>
      ))}
      {series.map((pts, k) => (
        <polyline
          key={k}
          fill="none"
          stroke={lineColors[k]}
          strokeWidth="2.5"
          strokeLinejoin="round"
          points={pts.map((v, i) => `${x(i)},${y(v)}`).join(" ")}
        />
      ))}
    </svg>
  );
}
