// Shared types and tiny presentation helpers. All finance logic lives in the FastAPI server.

export type Bucket = "emergency" | "stocks" | "bonds" | "cash" | "alt";
export const BUCKETS: Bucket[] = ["emergency", "stocks", "bonds", "cash", "alt"];

export type Goal = "wealth" | "house" | "business" | "income";
export type Horizon = 1 | 3 | 7 | 12;
export type Emergency = "none" | "insufficient" | "enough";
export type Debt = "none" | "some" | "significant";
export type Risk = 1 | 2 | 3;
export type ProductGroup = "Global Stocks (ETF)" | "Bonds" | "Savings";

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

export type Pct = Record<Bucket, number>;
export type Slice = { bucket: Bucket; pct: number; amount: number };

export type Product = {
  name: string;
  ticker: string;
  risk: number;
  fee: string;
  min: string;
  blurb: string;
  region: string; // where it invests, e.g. "US", "Worldwide"
  live: boolean; // false for accounts/funds with no market listing
};

// Live metrics per ticker from GET /api/market (all percents; fields missing when unavailable).
export type MarketItem = {
  price?: number;
  expense_ratio_pct?: number;
  yield_pct?: number;
  ret_1y_pct?: number;
  ret_3y_pct?: number;
  ret_5y_pct?: number;
  volatility_pct?: number;
  max_drawdown_pct?: number;
};
export type Market = { source: string; asof: string | null; items: Record<string, MarketItem> };
export type Source = { id: string; title: string; publisher: string; url: string };
export type Status = "good" | "ok" | "bad";
export type Analysis = {
  score: number;
  rows: { label: string; value: string; status: Status }[];
  insights: string[];
};
export type PlanResult = { base: Pct; limits: { min: Pct; max: Pct }; analysis: Analysis };

// Reference data served by GET /api/catalog.
export type Catalog = {
  labels: { goal: Record<string, string>; horizon: Record<string, string>; emergency: Record<string, string>; debt: Record<string, string>; risk: Record<string, string> };
  buckets: Record<Bucket, { label: string; why: string }>;
  group_buckets: Record<ProductGroup, Bucket[]>;
  products: Record<ProductGroup, Product[]>;
  sources: Record<string, Source>;
};

// What the advisor agent asks the website to do. Profile/goto apply immediately;
// allocation/products are proposals the user must accept.
export type Action =
  | { type: "profile"; updates: Partial<Profile> }
  | { type: "allocation"; before: Pct; after: Pct; reason: string; notes: string[] }
  | { type: "products"; group: ProductGroup; tickers: string[]; reason: string }
  | { type: "goto"; step: number };

export const BUCKET_COLORS: Record<Bucket, string> = {
  emergency: "#10b981",
  stocks: "#3b82f6",
  bonds: "#8b5cf6",
  cash: "#f59e0b",
  alt: "#f43f5e",
};

export const usd = (n: number) =>
  n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

// Display arithmetic only: dollars per bucket for a given percent split.
export function slicesFromPct(amount: number, pct: Pct): Slice[] {
  return BUCKETS.filter((b) => pct[b] > 0).map((bucket) => ({
    bucket,
    pct: pct[bucket],
    amount: Math.round((amount * pct[bucket]) / 100),
  }));
}

export const groupOf = (catalog: Catalog, ticker: string): ProductGroup | undefined =>
  (Object.keys(catalog.products) as ProductGroup[]).find((g) => catalog.products[g].some((p) => p.ticker === ticker));
