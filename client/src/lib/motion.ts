// Timing for Sprout's replies. A short, length-scaled delay with a typing indicator feels more
// human (Gnewuch et al. 2018), but long waits frustrate experienced users and break flow after
// about 1 second (Nielsen), so the delay is capped. Reduced-motion users get everything at once.

export function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** Total time the typing indicator should show for a reply of this length, in ms. */
export function typingDelayMs(reply: string): number {
  if (prefersReducedMotion()) return 0;
  return Math.min(1000, 350 + reply.length * 6);
}

/** Time between words while a reply appears: even pacing, whole reply in about 0.6 s. */
export function wordIntervalMs(words: number): number {
  return Math.max(12, Math.min(45, 600 / Math.max(words, 1)));
}

export const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

/** Run a request, then keep the typing indicator up for the rest of the reply's delay. */
export async function withTypingDelay<T extends { reply: string }>(request: () => Promise<T>): Promise<T> {
  const started = performance.now();
  const out = await request();
  const wait = typingDelayMs(out.reply) - (performance.now() - started);
  if (wait > 0) await sleep(wait);
  return out;
}
