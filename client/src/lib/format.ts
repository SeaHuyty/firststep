// Every number on screen goes through here (docs/standards/ui-spec.md section 3): one locale,
// a true minus sign (U+2212), signs on changes, and precision by context.
const MINUS = "−";

const whole = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});
const cents = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

function withMinus(text: string): string {
  return text.replace("-", MINUS);
}

function num(value: number | string): number {
  return typeof value === "string" ? Number(value) : value;
}

/** Plan amounts in whole dollars: "$6,000". */
export function money(value: number | string): string {
  return withMinus(whole.format(num(value)));
}

/** Receipts and prices to the cent: "$412.37". */
export function moneyCents(value: number | string): string {
  return withMinus(cents.format(num(value)));
}

/** A change, always signed: "+$1,200" or "−$340". */
export function moneyChange(value: number | string): string {
  const n = num(value);
  return n > 0 ? `+${whole.format(n)}` : withMinus(whole.format(n));
}

/** Weights as whole percents: "35%". */
export function pct(value: number): string {
  return `${Math.round(value)}%`;
}

/** Returns to one decimal, signed: "+4.2%", "−14.2%". */
export function pctChange(value: number): string {
  const text = `${Math.abs(value).toFixed(1)}%`;
  return value > 0 ? `+${text}` : value < 0 ? `${MINUS}${text}` : text;
}

/** Fees to two decimals: "0.07% a year". */
export function fee(valuePct: number): string {
  return `${valuePct.toFixed(2)}% a year`;
}

/** A probability as a whole percent, never "0%" for a small chance: "about 1 in 5". */
export function chance(p: number): string {
  if (p <= 0) return "none in our replays";
  if (p < 0.01) return "under 1%";
  return `${Math.round(p * 100)}%`;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** A simulated month "2020-03" as "Mar 2020". */
export function month(ym: string): string {
  const [y, m] = ym.split("-");
  return `${MONTHS[Number(m) - 1] ?? ""} ${y ?? ""}`.trim();
}

/** "7 months", "1 month", "1 year 8 months". */
export function duration(months: number): string {
  const y = Math.floor(months / 12);
  const m = months % 12;
  const part = (n: number, unit: string) => `${n} ${unit}${n === 1 ? "" : "s"}`;
  if (y === 0) return part(m, "month");
  return m === 0 ? part(y, "year") : `${part(y, "year")} ${part(m, "month")}`;
}
