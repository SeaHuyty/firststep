"use client";

// Sprout's voice, shared by the chat and the welcome page so both look like one conversation.
import { useEffect, useState } from "react";
import { THINKING } from "@/lib/copy";
import { prefersReducedMotion, wordIntervalMs } from "@/lib/motion";

export const BUBBLE = "max-w-[60ch] rounded-md rounded-tl-sm border border-line bg-surface px-4 py-3 text-body-lg text-ink";

export function Avatar() {
  // eslint-disable-next-line @next/next/no-img-element -- a 32px SVG avatar
  return <img src="/brand/sprout-avatar.svg" alt="" width={32} height={32} className="mt-1 size-8 shrink-0" />;
}

/** Words appear at an even pace; the full text is in the DOM from the start, so the bubble
 * never jumps in size and screen readers get the whole sentence at once. */
export function RevealText({ text, onDone, onTick }: { text: string; onDone: () => void; onTick: () => void }) {
  const words = text.split(" ");
  const [count, setCount] = useState(prefersReducedMotion() ? words.length : 0);
  useEffect(() => {
    if (count >= words.length) {
      const t = setTimeout(onDone, 0);
      return () => clearTimeout(t);
    }
    let n = count;
    const timer = setInterval(() => {
      n += 1;
      setCount(n);
      onTick();
      if (n >= words.length) {
        clearInterval(timer);
        onDone();
      }
    }, wordIntervalMs(words.length));
    return () => clearInterval(timer);
    // Run once per text; `count` only seeds the start.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text]);
  return (
    <>
      <span className="sr-only">{text}</span>
      <span aria-hidden>
        {words.slice(0, count).join(" ")}
        <span className="opacity-0"> {words.slice(count).join(" ")}</span>
      </span>
    </>
  );
}

export function TypingIndicator() {
  return (
    <div className="flex gap-3 animate-fade" role="status">
      <Avatar />
      <p className="flex h-12 items-center gap-1.5 rounded-md rounded-tl-sm border border-line bg-surface px-4">
        <span className="sr-only">{THINKING}</span>
        {[0, 1, 2].map((i) => (
          <span key={i} aria-hidden className="typing-dot size-2 rounded-full bg-primary" />
        ))}
      </p>
    </div>
  );
}
