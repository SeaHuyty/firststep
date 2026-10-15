import type { Bucket } from "./plan";

// Curated trusted sources. URLs verified to exist; summaries are paraphrases
// of what each page covers. The LLM may cite only these ids.
export type Source = {
  id: string;
  title: string;
  publisher: string;
  url: string;
  summary: string;
};

export const sources: Record<string, Source> = {
  S1: {
    id: "S1",
    title: "Asset Allocation and Diversification",
    publisher: "SEC Investor.gov",
    url: "https://www.investor.gov/introduction-investing/getting-started/asset-allocation",
    summary:
      "Asset allocation splits a portfolio among categories like stocks, bonds and cash. The right mix depends on time horizon and risk tolerance; longer horizons may suit riskier, more volatile holdings, shorter ones less volatile options.",
  },
  S2: {
    id: "S2",
    title: "Beginners’ Guide to Asset Allocation, Diversification, and Rebalancing",
    publisher: "SEC Investor.gov",
    url: "https://www.investor.gov/additional-resources/general-resources/publications-research/info-sheets/beginners-guide-asset",
    summary:
      "A portfolio should be diversified both between and within asset categories. The most common reason to change an allocation is a change in time horizon.",
  },
  S3: {
    id: "S3",
    title: "Exchange-Traded Funds (ETFs)",
    publisher: "SEC Investor.gov",
    url: "https://www.investor.gov/introduction-investing/investing-basics/investment-products/mutual-funds-and-exchange-traded-2",
    summary:
      "ETF shares trade on exchanges throughout the day. ETFs have tended to cost less to run than comparable mutual funds; bid-ask spreads, premiums/discounts and brokerage commissions can affect what an investor pays.",
  },
  S4: {
    id: "S4",
    title: "Bonds - FAQs",
    publisher: "SEC Investor.gov",
    url: "https://www.investor.gov/introduction-investing/investing-basics/investment-products/bonds-or-fixed-income-products/bonds",
    summary:
      "A bond is a loan to an issuer in exchange for interest and return of principal. When market interest rates rise, prices of fixed-rate bonds fall; bonds and bond funds are not risk-free.",
  },
  S5: {
    id: "S5",
    title: "An essential guide to building an emergency fund",
    publisher: "CFPB",
    url: "https://www.consumerfinance.gov/an-essential-guide-to-building-an-emergency-fund/",
    summary:
      "How much to keep in emergency savings depends on personal circumstances; a good starting point is the typical unexpected costs you have faced before.",
  },
  S6: {
    id: "S6",
    title: "Your Money, Your Goals: workers toolkit",
    publisher: "CFPB",
    url: "https://files.consumerfinance.gov/f/YMYG_Workers_Toolkit_Emp_4-28-16_machine_readable_a.pdf",
    summary: "Recommends keeping three to six months’ worth of living expenses in emergency savings.",
  },
  S7: {
    id: "S7",
    title: "Introduction to Investing",
    publisher: "SEC Investor.gov",
    url: "https://www.investor.gov/introduction-investing",
    summary:
      "The right mix depends on risk tolerance and time horizon. Money needed soon, such as a near-term down payment, calls for lower-risk holdings like money market funds or CDs.",
  },
};

const byBucket: Record<Bucket, string[]> = {
  emergency: ["S5", "S6"],
  stocks: ["S1", "S3", "S2"],
  bonds: ["S4", "S2"],
  cash: ["S7", "S1"],
  alt: ["S2"],
};

export function sourcesFor(buckets: Bucket[]): Source[] {
  const ids = new Set<string>(["S1"]);
  buckets.forEach((b) => byBucket[b].forEach((id) => ids.add(id)));
  return [...ids].map((id) => sources[id]);
}

export function sourceIdsFor(bucket: Bucket): string[] {
  return byBucket[bucket];
}
