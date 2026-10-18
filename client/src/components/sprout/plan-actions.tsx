"use client";

// What the plan's cards can ask Sprout to do, without each card knowing about the session.
import { createContext, useContext } from "react";

export type PlanActions = {
  /** Put funds side by side; `label` is what the person "says" in the chat. */
  compare: (productIds: string[], label: string) => void;
  busy: boolean;
};

export const PlanActionsContext = createContext<PlanActions | null>(null);

export const usePlanActions = () => useContext(PlanActionsContext);
