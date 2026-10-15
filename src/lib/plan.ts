// Mock advisory logic. Frontend-only prototype: no real financial advice.

export type Goal = "wealth" | "house" | "business" | "income";
export type Horizon = 1 | 3 | 7 | 12; // representative years for each range
export type Emergency = "none" | "insufficient" | "enough";
export type Debt = "none" | "some" | "significant";
export type Risk = 1 | 2 | 3;

export type Profile = {
  amount: number;
  goal: Goal;
  horizon: Horizon;
  emergency: Emergency;
  risk: Risk;
  debt: Debt;
};

export const defaultProfile: Profile = {
  amount: 10000,
  goal: "wealth",
  horizon: 7,
  emergency: "insufficient",
  risk: 2,
  debt: "none",
};

export const goalLabels: Record<Goal, string> = {
  wealth: "Build wealth",
  house: "Buy a house",
  business: "Start a business",
  income: "Regular income",
};

export const horizonLabels: Record<Horizon, string> = {
  1: "Under 2 years",
  3: "2–5 years",
  7: "5–10 years",
  12: "10+ years",
};

export const emergencyLabels: Record<Emergency, string> = {
  none: "No emergency savings",
  insufficient: "Some, but possibly insufficient",
  enough: "6+ months covered",
};

export const debtLabels: Record<Debt, string> = {
  none: "No significant debt",
  some: "Some manageable debt",
  significant: "Significant debt",
};

export const riskLabels: Record<Risk, string> = {
  1: "Conservative",
  2: "Moderate",
  3: "Aggressive",
};

export type Bucket = "emergency" | "stocks" | "bonds" | "cash" | "alt";

export const bucketMeta: Record<
  Bucket,
  { label: string; color: string; why: string }
> = {
  emergency: {
    label: "Emergency Fund",
    color: "#10b981",
    why: "A safety cushion for unexpected expenses (3–6 months).",
  },
  stocks: {
    label: "Global Stocks (ETF)",
    color: "#3b82f6",
    why: "Long-term growth through diversified global equities.",
  },
  bonds: {
    label: "Bonds / Fixed Income",
    color: "#8b5cf6",
    why: "Adds stability and reduces overall volatility.",
  },
  cash: {
    label: "Cash / High-yield Savings",
    color: "#f59e0b",
    why: "Liquidity for near-term needs and opportunities.",
  },
  alt: {
    label: "Alternatives (e.g. REITs)",
    color: "#f43f5e",
    why: "Optional extra diversification beyond stocks and bonds.",
  },
};

export type Slice = { bucket: Bucket; pct: number; amount: number };

export function allocate(p: Profile): Slice[] {
  const emergency =
    { none: 30, insufficient: 20, enough: 5 }[p.emergency] +
    (p.debt === "significant" ? 5 : 0);
  const rest = 100 - emergency;

  const base = { 1: 0.25, 2: 0.5, 3: 0.7 }[p.risk];
  const adj = p.horizon === 1 ? -0.25 : p.horizon === 3 ? -0.1 : p.horizon === 12 ? 0.1 : 0;
  const stockShare = Math.min(0.85, Math.max(0.05, base + adj));

  const alt = p.risk >= 2 && p.horizon >= 7 ? 5 : 0;
  const stocks = Math.round(rest * stockShare);
  const bonds = Math.round(Math.max(0, rest - alt - stocks) * 0.65);
  const cash = 100 - emergency - alt - stocks - bonds;

  const pcts: Record<Bucket, number> = { emergency, stocks, bonds, cash, alt };
  return (Object.keys(pcts) as Bucket[])
    .filter((b) => pcts[b] > 0)
    .map((bucket) => ({
      bucket,
      pct: pcts[bucket],
      amount: Math.round((p.amount * pcts[bucket]) / 100),
    }));
}

export type Status = "good" | "ok" | "bad";

export function analyse(p: Profile) {
  const emergencyPts = { none: 0, insufficient: 15, enough: 30 }[p.emergency];
  const debtPts = { none: 20, some: 10, significant: 0 }[p.debt];
  const horizonPts = p.horizon >= 7 ? 10 : p.horizon === 3 ? 5 : 0;
  const score = 40 + emergencyPts + debtPts + horizonPts;

  const rows: { label: string; value: string; status: Status }[] = [
    {
      label: "Debt level",
      value: { none: "Low", some: "Moderate", significant: "High" }[p.debt],
      status: { none: "good", some: "ok", significant: "bad" }[p.debt] as Status,
    },
    {
      label: "Emergency fund",
      value: { none: "Missing", insufficient: "Needs improvement", enough: "Good" }[p.emergency],
      status: { none: "bad", insufficient: "ok", enough: "good" }[p.emergency] as Status,
    },
    {
      label: "Time horizon",
      value: p.horizon >= 7 ? "Long" : p.horizon === 3 ? "Medium" : "Short",
      status: (p.horizon >= 7 ? "good" : p.horizon === 3 ? "ok" : "bad") as Status,
    },
  ];

  const insights: string[] = [];
  if (p.emergency !== "enough")
    insights.push("Your emergency savings may not cover 6 months of expenses.");
  if (p.debt !== "none")
    insights.push("Paying down debt first can beat most investment returns.");
  if (p.horizon >= 7)
    insights.push("A long horizon allows more growth-oriented investments.");
  else insights.push("A short horizon calls for safer, more liquid holdings.");

  return { score, rows, insights };
}

export type ProductGroup = "Global Stocks (ETF)" | "Bonds" | "Savings";

// Which plan buckets each product tab covers.
export const groupBuckets: Record<ProductGroup, Bucket[]> = {
  "Global Stocks (ETF)": ["stocks", "alt"],
  Bonds: ["bonds"],
  Savings: ["emergency", "cash"],
};

export const products: Record<
  ProductGroup,
  { name: string; ticker: string; risk: 1 | 2 | 3 | 4 | 5; fee: string; min: string; blurb: string }[]
> = {
  "Global Stocks (ETF)": [
    { name: "Vanguard S&P 500 ETF", ticker: "VOO", risk: 3, fee: "0.03%", min: "~$100", blurb: "Tracks 500 large U.S. companies. Long-term growth with diversified exposure." },
    { name: "iShares Core MSCI World ETF", ticker: "IWDA", risk: 3, fee: "0.20%", min: "~$100", blurb: "Diversified exposure across developed markets." },
    { name: "Invesco NASDAQ 100 ETF", ticker: "QQQM", risk: 4, fee: "0.15%", min: "~$100", blurb: "Leading technology companies. Higher potential return, higher volatility." },
  ],
  Bonds: [
    { name: "Vanguard Total Bond Market ETF", ticker: "BND", risk: 2, fee: "0.03%", min: "~$100", blurb: "Broad U.S. investment-grade bonds for stability." },
    { name: "iShares Core U.S. Aggregate Bond ETF", ticker: "AGG", risk: 2, fee: "0.03%", min: "~$100", blurb: "Diversified bond exposure with steady income." },
  ],
  Savings: [
    { name: "High-yield Savings Account", ticker: "HYSA", risk: 1, fee: "None", min: "$0", blurb: "Instant access, insured deposits. Good home for an emergency fund." },
    { name: "Money Market Fund", ticker: "MMF", risk: 1, fee: "~0.10%", min: "~$500", blurb: "Short-term, low-risk securities with competitive yield." },
  ],
};

// Annual return assumptions [pessimistic, base, optimistic] per risk level.
const rates: Record<Risk, [number, number, number]> = {
  1: [0.01, 0.03, 0.05],
  2: [0.0, 0.05, 0.08],
  3: [-0.02, 0.07, 0.11],
};

export function project(amount: number, monthly: number, years: number, risk: Risk) {
  return rates[risk].map((annual) => {
    const r = annual / 12;
    const points: number[] = [];
    for (let y = 0; y <= years; y++) {
      const n = y * 12;
      const fv =
        r === 0
          ? amount + monthly * n
          : amount * Math.pow(1 + r, n) + (monthly * (Math.pow(1 + r, n) - 1)) / r;
      points.push(Math.round(fv));
    }
    return points;
  }) as [number[], number[], number[]];
}

export const usd = (n: number) =>
  n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
