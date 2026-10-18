// Small building blocks. Cards are bordered, never shadowed (docs/standards/brand.md section 7).
import { CircleAlert, CircleCheck, Info, Pause } from "lucide-react";
import type { ReactNode } from "react";
import { RuleNote } from "./rule-note";

export function Card({
  title,
  overline,
  children,
  className = "",
}: {
  title?: ReactNode;
  overline?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded-md border border-line bg-surface p-4 md:p-5 ${className}`}>
      {overline && <p className="text-overline uppercase text-muted">{overline}</p>}
      {title && <h3 className="mt-1 text-title text-ink">{title}</h3>}
      <div className={title || overline ? "mt-3" : ""}>{children}</div>
    </section>
  );
}

/** A rule ID in mono, so a judge can trace it to rules.yaml, code and logs. */
export function RuleChip({ id }: { id: string }) {
  return (
    <span className="inline-flex shrink-0 items-center rounded-full border border-border-strong bg-sunken px-2 font-mono text-mono text-ink-2">
      {id}
    </span>
  );
}

const RISK_BG = ["", "bg-risk-1", "bg-risk-2", "bg-risk-3", "bg-risk-4", "bg-risk-5"];
const RISK_INK = ["", "text-ink", "text-ink", "text-ink", "text-on-primary", "text-on-primary"];

/** C1-C5 or R1-R5 on one teal ladder: more risk is "more", never "bad". Number plus a word. */
export function RiskBadge({ code, label }: { code: string; label?: string }) {
  const level = Number(code.slice(1)) || 1;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-label ${RISK_BG[level]} ${RISK_INK[level]}`}
    >
      <span className="font-mono text-mono">{code}</span>
      {label && <span>{label}</span>}
    </span>
  );
}

type Tone = "info" | "success" | "pause" | "error";

const TONE: Record<Tone, { box: string; icon: ReactNode }> = {
  info: { box: "border-line bg-surface", icon: <Info aria-hidden className="size-5 text-primary" /> },
  success: {
    box: "border-primary bg-primary-soft",
    icon: <CircleCheck aria-hidden className="size-5 text-primary" />,
  },
  pause: { box: "border-sun bg-sun-soft", icon: <Pause aria-hidden className="size-5 text-sun-ink" /> },
  error: {
    box: "border-danger bg-danger-soft",
    icon: <CircleAlert aria-hidden className="size-5 text-danger" />,
  },
};

/** Icon + title + one sentence, so tone never relies on colour alone. Amber is never an error. */
export function Notice({
  tone,
  title,
  children,
  ruleId,
  action,
}: {
  tone: Tone;
  title: string;
  children?: ReactNode;
  ruleId?: string | null;
  action?: ReactNode;
}) {
  return (
    <div role={tone === "error" ? "alert" : "status"} className={`rounded-md border p-4 ${TONE[tone].box}`}>
      <div className="flex items-start gap-3">
        <span className="mt-0.5">{TONE[tone].icon}</span>
        <div className="min-w-0 flex-1">
          <p className={`text-title ${tone === "pause" ? "text-sun-ink" : "text-ink"}`}>{title}</p>
          {children && <div className="mt-1 text-body text-ink-2">{children}</div>}
          {ruleId && <RuleNote ids={[ruleId]} />}
          {action && <div className="mt-3">{action}</div>}
        </div>
      </div>
    </div>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div aria-hidden className={`animate-pulse rounded-sm bg-sunken ${className}`} />;
}

/** A labelled table alternative for every chart (WCAG: charts have a text equivalent). */
export function DataTable({
  caption,
  head,
  rows,
}: {
  caption: string;
  head: string[];
  rows: (string | number)[][];
}) {
  return (
    <details className="mt-3 text-body-sm">
      <summary className="cursor-pointer text-primary">Show as a table</summary>
      <table className="mt-2 w-full border-collapse">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="border-b border-line text-left text-muted">
            {head.map((h, i) => (
              <th key={h} scope="col" className={`py-1 font-medium ${i > 0 ? "text-right" : ""}`}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={String(row[0])} className="border-b border-line last:border-0">
              {row.map((cell, i) => (
                <td key={i} className={`py-1 ${i > 0 ? "tnum text-right" : ""}`}>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}
