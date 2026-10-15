import type { Pct, Profile, ProductGroup } from "./plan";

// What the advisor agent asks the website to do. Profile/goto apply immediately;
// allocation/products are proposals the user must accept.
export type Action =
  | { type: "profile"; updates: Partial<Profile> }
  | { type: "allocation"; before: Pct; after: Pct; reason: string; notes: string[] }
  | { type: "products"; group: ProductGroup; tickers: string[]; reason: string }
  | { type: "goto"; step: number };

export const STEP_NAMES = ["info", "analysis", "plan", "products", "whatif"] as const;
