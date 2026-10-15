import { streamText, type LanguageModel } from "ai";
import { anthropic } from "@ai-sdk/anthropic";
import { google } from "@ai-sdk/google";
import { z } from "zod";
import {
  allocate,
  analyse,
  bucketMeta,
  debtLabels,
  emergencyLabels,
  goalLabels,
  horizonLabels,
  riskLabels,
  usd,
  type Profile,
} from "@/lib/plan";
import { sourceIdsFor, sourcesFor } from "@/lib/sources";

const profileSchema = z.object({
  amount: z.number().min(0).max(100_000_000),
  goal: z.enum(["wealth", "house", "business", "income"]),
  horizon: z.union([z.literal(1), z.literal(3), z.literal(7), z.literal(12)]),
  emergency: z.enum(["none", "insufficient", "enough"]),
  risk: z.union([z.literal(1), z.literal(2), z.literal(3)]),
  debt: z.enum(["none", "some", "significant"]),
});

// Claude if ANTHROPIC_API_KEY is set, else Gemini free tier, else null (canned fallback).
function pickModel(): LanguageModel | null {
  if (process.env.ANTHROPIC_API_KEY) return anthropic(process.env.ANTHROPIC_MODEL ?? "claude-sonnet-5-5");
  if (process.env.GOOGLE_GENERATIVE_AI_API_KEY) return google(process.env.GEMINI_MODEL ?? "gemini-3.8-flash");
  return null;
}

const SYSTEM = `You are the explanation layer of an AI wealth advisor prototype.
The allocation was already decided by deterministic code. Never change, question or recalculate it; only explain it.
Write one short paragraph (2 sentences max) per allocation bucket, in the order given, each starting with the bucket name in bold-free plain text followed by a colon.
Ground every factual claim in the provided SOURCES and cite with the marker [S#] right after the claim. Cite only source ids that appear in SOURCES. Do not invent facts, figures, returns or URLs.
Tie each explanation to the client's profile (goal, horizon, risk, emergency savings, debt).
Plain language, no markdown, no guarantees of returns. Finish with one sentence saying this is educational, not personalised financial advice.`;

function fallbackText(p: Profile): string {
  const slices = allocate(p);
  const body = slices
    .map((s) => {
      const cites = sourceIdsFor(s.bucket).map((id) => `[${id}]`).join("");
      return `${bucketMeta[s.bucket].label}: ${usd(s.amount)} (${s.pct}%). ${bucketMeta[s.bucket].why} ${cites}`;
    })
    .join("\n\n");
  return `${body}\n\n(Demo explanation: no AI key configured. Add GOOGLE_GENERATIVE_AI_API_KEY or ANTHROPIC_API_KEY for a personalised one.) This is educational, not personalised financial advice.`;
}

export async function POST(req: Request) {
  const parsed = profileSchema.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return Response.json({ error: "Invalid profile" }, { status: 400 });
  const profile: Profile = parsed.data;

  const slices = allocate(profile);
  const model = pickModel();
  if (!model) return new Response(fallbackText(profile), { headers: { "Content-Type": "text/plain; charset=utf-8" } });

  const { score } = analyse(profile);
  const prompt = `CLIENT PROFILE
- Available money: ${usd(profile.amount)}
- Goal: ${goalLabels[profile.goal]}
- Time horizon: ${horizonLabels[profile.horizon]}
- Risk tolerance: ${riskLabels[profile.risk]}
- Emergency savings: ${emergencyLabels[profile.emergency]}
- Debt: ${debtLabels[profile.debt]}
- Financial health score: ${score}/100

ALLOCATION (fixed)
${slices.map((s) => `- ${bucketMeta[s.bucket].label}: ${usd(s.amount)} (${s.pct}%)`).join("\n")}

SOURCES
${sourcesFor(slices.map((s) => s.bucket))
  .map((s) => `[${s.id}] ${s.publisher}, "${s.title}": ${s.summary}`)
  .join("\n")}`;

  const result = streamText({
    model,
    system: SYSTEM,
    prompt,
    // Explaining a fixed allocation needs no deep reasoning; low thinking effort is much faster.
    providerOptions: { google: { thinkingConfig: { thinkingLevel: "low" } } },
  });
  return result.toTextStreamResponse();
}
