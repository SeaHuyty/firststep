"use client";

import { Fragment, useEffect, useState } from "react";
import { streamExplanation } from "@/lib/api";
import { useCatalog } from "@/lib/catalog";
import type { Pct, Profile } from "@/lib/types";

// Matches [S1] and also combined markers like [S1, S3].
const MARKER = /(\[S\d+(?:\s*,\s*S\d+)*\])/g;
const idsIn = (marker: string) => marker.match(/S\d+/g) ?? [];

function Cited({ text }: { text: string }) {
  const { sources } = useCatalog();
  return (
    <>
      {text.split(MARKER).map((part, i) => {
        if (!part.startsWith("[S")) return <Fragment key={i}>{part}</Fragment>;
        return (
          <Fragment key={i}>
            {idsIn(part)
              .filter((id) => sources[id])
              .map((id) => (
                <a
                  key={id}
                  href={sources[id].url}
                  target="_blank"
                  rel="noreferrer"
                  title={`${sources[id].publisher}: ${sources[id].title}`}
                  className="align-super text-[10px] font-medium text-blue-600 hover:underline"
                >
                  [{id}]
                </a>
              ))}
          </Fragment>
        );
      })}
    </>
  );
}

// Remount with a new `key` when the inputs change; the effect only sets state from async callbacks.
export function Explanation({ profile, pct }: { profile: Profile; pct: Pct }) {
  const { sources } = useCatalog();
  const [text, setText] = useState("");
  const [state, setState] = useState<"loading" | "done" | "error">("loading");

  useEffect(() => {
    const ctrl = new AbortController();
    streamExplanation({ profile, pct }, setText, ctrl.signal).then(
      (full) => setState(full.trim() ? "done" : "error"),
      () => {
        if (!ctrl.signal.aborted) setState("error");
      },
    );
    return () => ctrl.abort();
  }, [profile, pct]);

  const cited = [...new Set((text.match(MARKER) ?? []).flatMap(idsIn))].filter((id) => sources[id]);

  return (
    <section>
      <h2 className="mb-3 mt-8 font-medium text-slate-900">Why this allocation?</h2>
      {state === "error" && (
        <p className="text-sm text-rose-600">Couldn’t generate the explanation. Check the server and your API key.</p>
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
