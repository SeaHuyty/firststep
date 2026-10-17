// Shared strings. Voice rules: docs/standards/brand.md section 3.
import type { Stage } from "./types";

export const DISCLOSURE = "Educational simulation. Not financial advice. No real money moves.";

export const STEPS = ["Check", "Profile", "Goal", "Plan", "Confirm", "Watch"] as const;
export type Step = (typeof STEPS)[number];

export const STEP_OF: Record<Stage, Step> = {
  ONBOARD: "Check",
  READINESS: "Check",
  SAVINGS_PLAN: "Check",
  PROFILE: "Profile",
  GOAL: "Goal",
  PROPOSE: "Plan",
  CONFIRM: "Confirm",
  EXECUTED: "Watch",
  MONITOR: "Watch",
};

export const FAMILY_LABEL: Record<string, string> = {
  cash: "Cash",
  bonds: "Bonds",
  stocks: "Stocks",
  gold: "Gold",
};

export const RULE_TITLE: Record<string, string> = {
  "SUIT-01": "Product risk within your level",
  "READY-01": "Emergency fund first",
  "READY-02": "Expensive debt first",
  "HOR-01": "Short goals stay cautious",
  "CONC-01": "Diversification limits",
  "LIM-01": "Sandbox order limits",
  "CONF-01": "You confirm every trade",
  "COOL-01": "Cooling-off before a panic sale",
  "DRIFT-01": "Rebalance when the mix drifts",
  "STAGE-01": "One step at a time",
};

export const PROMISES = [
  { title: "We check your money health first", text: "If now isn't the time, Sprout says so and makes a plan." },
  { title: "We show ranges, not predictions", text: "A bad, a typical and a good case, from past markets." },
  { title: "Nothing happens without your OK", text: "Every order waits for you to press Confirm." },
];

export const THINKING = "Sprout is thinking…";
