"use client";

import { Fragment, useEffect, useState } from "react";
import { sources } from "@/lib/sources";
import type { Pct, Profile } from "@/lib/plan";

function Cited({ text }: { text: string }) {
  return (
    <>
      {text.split(/(\[S\d+\])/g).map((part, i) => {
        const src = sources[part.slice(1, -1)];
        if (!src || !part.startsWith("[")) return <Fragment key={i}>{part}</Fragment>;
        return (
          <a
            key={i}
            href={src.url}
            target="_blank"
            rel="noreferrer"
            title={`${src.publisher}: ${src.title}`}
            className="align-super text-[10px] font-medium text-blue-600 hover:underline"
          >
            [{src.id}]
          </a>
        );
      })}
    </>
  );
}

// Remount with a new `key` when the profile changes; effect only sets state from async callbacks.
export function Explanation({ profile, pct }: { profile: Profile; pct: Pct }) {
  const [text, setText] = useState("");
  const [state, setState] = useState<"loading" | "done" | "error">("loading");

  useEffect(() => {
    const ctrl = new AbortController();
    (async () => {
      try {
        const res = await fetch("/api/explain", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ profile, pct }),
          signal: ctrl.signal,
        });
        if (!res.ok || !res.body) throw new Error(String(res.status));
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let acc = "";
        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          acc += decoder.decode(value, { stream: true });
          setText(acc);
        }
        setState(acc.trim() ? "done" : "error");
      } catch {
        if (!ctrl.signal.aborted) setState("error");
      }
    })();
    return () => ctrl.abort();
  }, [profile, pct]);

  const cited = [...new Set([...text.matchAll(/\[(S\d+)\]/g)].map((m) => m[1]))].filter((id) => sources[id]);

  return (
    <section>
      <h2 className="mb-3 mt-8 font-medium text-slate-900">Why this allocation?</h2>
      {state === "error" && (
        <p className="text-sm text-rose-600">Couldn’t generate the explanation. Check your API key and try again.</p>
      )}
      {state === "loading" && !text && <p className="text-sm text-slate-500">Writing explanation…</p>}
      <div className="space-y-3 text-sm leading-relaxed text-slate-700">
        {text
          .split(/\n{2,}/)
          .filter(Boolean)
          .map((para, i) => (
            <p key={i}>
              <Cited text={para} />
            </p>
          ))}
      </div>
      {cited.length > 0 && (
        <div className="mt-5 rounded-lg bg-slate-50 p-4">
          <h3 className="text-xs font-medium uppercase tracking-wide text-slate-500">Sources</h3>
          <ul className="mt-2 space-y-1 text-xs text-slate-600">
            {cited.map((id) => (
              <li key={id}>
                <span className="font-medium text-slate-900">[{id}]</span>{" "}
                <a href={sources[id].url} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline">
                  {sources[id].publisher}: {sources[id].title}
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
