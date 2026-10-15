"use client";

import { useEffect, useRef, useState } from "react";
import type { Profile } from "@/lib/plan";

type Msg = { role: "user" | "assistant"; content: string };

const GREETING: Msg = {
  role: "assistant",
  content: "Hi, I’m your AI advisor. How much money do you have available to invest, and what is it for?",
};
const TOTAL = 6;

export function Chat({
  profile,
  setProfile,
  onNext,
}: {
  profile: Profile;
  setProfile: (p: Profile) => void;
  onNext: () => void;
}) {
  const [messages, setMessages] = useState<Msg[]>([GREETING]);
  const [known, setKnown] = useState<Partial<Profile>>({});
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [complete, setComplete] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages, busy]);

  async function send() {
    const text = input.trim();
    if (!text || busy) return;
    const next: Msg[] = [...messages, { role: "user", content: text }];
    setMessages(next);
    setInput("");
    setBusy(true);
    setError("");
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: next, known }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "Something went wrong.");
      setMessages([...next, { role: "assistant", content: data.reply }]);
      setKnown(data.known);
      setComplete(data.complete);
      setProfile({ ...profile, ...data.known });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  const count = Object.keys(known).length;

  return (
    <div className="flex h-[min(34rem,70vh)] flex-col rounded-xl border border-slate-200">
      <div className="flex-1 space-y-3 overflow-y-auto p-4" aria-live="polite">
        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "flex justify-end" : "flex"}>
            <p
              className={`max-w-[85%] rounded-2xl px-3.5 py-2 text-sm leading-relaxed ${
                m.role === "user" ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-800"
              }`}
            >
              {m.content}
            </p>
          </div>
        ))}
        {busy && <p className="text-xs text-slate-400">Thinking…</p>}
        {error && <p className="text-xs text-rose-600">{error}</p>}
        <div ref={endRef} />
      </div>

      <div className="border-t border-slate-200 p-3">
        {complete ? (
          <button
            onClick={onNext}
            className="w-full rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-700"
          >
            Analyse my situation →
          </button>
        ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              send();
            }}
            className="flex gap-2"
          >
            <input
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
              placeholder="Type your answer…"
              value={input}
              maxLength={500}
              onChange={(e) => setInput(e.target.value)}
            />
            <button
              disabled={busy || !input.trim()}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-40"
            >
              Send
            </button>
          </form>
        )}
        <p className="mt-2 text-xs text-slate-400">
          {count} of {TOTAL} details collected
        </p>
      </div>
    </div>
  );
}
