"use client";

// Explain in place: a dotted word opens a two-sentence definition right there, so nobody has to
// leave the page to learn a term (docs/standards/onboarding-ux.md principle 4). Definitions come
// from the server's fixed, cited glossary, never from the LLM.
import { createContext, type ReactNode, use, useEffect, useId, useState } from "react";

type Entry = { term: string; text: string; source: string };
type Glossary = { terms: Record<string, Entry>; sources: Record<string, { title: string; url: string }> };

const GlossaryContext = createContext<Glossary | null>(null);

export function GlossaryProvider({ children }: { children: ReactNode }) {
  const [glossary, setGlossary] = useState<Glossary | null>(null);
  useEffect(() => {
    let live = true;
    fetch("/api/catalog")
      .then((r) => (r.ok ? r.json() : null))
      .then((data: { glossary: Glossary["terms"]; sources: Glossary["sources"] } | null) => {
        if (live && data) setGlossary({ terms: data.glossary, sources: data.sources });
      })
      .catch(() => undefined); // without definitions the words still read as plain text
    return () => {
      live = false;
    };
  }, []);
  return <GlossaryContext value={glossary}>{children}</GlossaryContext>;
}

export function Term({ id, children }: { id: string; children: ReactNode }) {
  const glossary = use(GlossaryContext);
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const entry = glossary?.terms[id];
  if (!entry) return <>{children}</>;
  const source = glossary.sources[entry.source];
  return (
    <span className="relative inline">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen(!open)}
        className="cursor-help rounded-sm text-inherit underline decoration-primary decoration-dotted decoration-2 underline-offset-4"
      >
        {children}
      </button>
      {open && (
        <span
          id={panelId}
          role="note"
          className="animate-rise absolute top-full left-0 z-20 mt-2 block w-72 rounded-md border border-line bg-surface p-3 text-left text-body-sm text-ink-2 shadow-popover"
        >
          <span className="block text-label text-ink">{entry.term}</span>
          <span className="mt-1 block">{entry.text}</span>
          {source && (
            <a href={source.url} target="_blank" rel="noreferrer" className="mt-2 block text-caption text-primary underline">
              Source: {source.title}
            </a>
          )}
        </span>
      )}
    </span>
  );
}
