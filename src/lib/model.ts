import type { LanguageModel } from "ai";
import { anthropic } from "@ai-sdk/anthropic";
import { google } from "@ai-sdk/google";

// Claude if ANTHROPIC_API_KEY is set, else Gemini free tier, else null.
// "chat" turns need low latency, so they default to lite models; "explain" favours quality.
export function pickModel(kind: "chat" | "explain" = "explain"): LanguageModel | null {
  if (process.env.ANTHROPIC_API_KEY) {
    return anthropic(
      kind === "chat"
        ? (process.env.ANTHROPIC_CHAT_MODEL ?? "claude-haiku-5-5")
        : (process.env.ANTHROPIC_MODEL ?? "claude-sonnet-5-5"),
    );
  }
  if (process.env.GOOGLE_GENERATIVE_AI_API_KEY) {
    return google(
      kind === "chat"
        ? (process.env.GEMINI_CHAT_MODEL ?? "gemini-3.5-flash-lite")
        : (process.env.GEMINI_MODEL ?? "gemini-3.8-flash"),
    );
  }
  return null;
}

// Our tasks (explaining, extracting facts) need no deep reasoning; low effort is much faster.
export const fastProviderOptions = { google: { thinkingConfig: { thinkingLevel: "low" as const } } };
// Chat runs several model calls per turn (tool loop) on a lite model, so skip thinking entirely.
export const chatProviderOptions = { google: { thinkingConfig: { thinkingLevel: "minimal" as const } } };
