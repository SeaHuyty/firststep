// Names for the generated API types. Never hand-write a type the backend defines:
// regenerate with `npm run gen:api` after changing the server.
import type { components } from "./api-types";

type S = components["schemas"];

export type SessionView = S["SessionView"];
export type TurnOut = S["TurnOut"];
export type Message = S["Message"];
export type PersonaHint = S["PersonaHint"];
export type AuditView = S["AuditView"];
export type Card = Message["cards"][number];
export type CardOf<T extends Card["type"]> = Extract<Card, { type: T }>;
export type Stage =
  | "ONBOARD"
  | "READINESS"
  | "SAVINGS_PLAN"
  | "PROFILE"
  | "GOAL"
  | "PROPOSE"
  | "CONFIRM"
  | "EXECUTED"
  | "MONITOR";
