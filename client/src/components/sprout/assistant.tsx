"use client";

// Sprout as an assistant you open, not the page itself: a floating button on every screen and a
// panel that slides in (the team's sketch; the pattern of support chat in Betterment and most
// banking apps). The panel holds the whole conversation; questions are answered on the page.
import { MessageCircle, X } from "lucide-react";
import { type ReactNode, useEffect, useRef } from "react";
import { Avatar } from "./bubble";

export function Assistant({
  open,
  onOpen,
  onClose,
  unread,
  children,
  composer,
}: {
  open: boolean;
  onOpen: () => void;
  onClose: () => void;
  /** Sprout said something while the panel was closed. */
  unread: boolean;
  children: ReactNode;
  composer: ReactNode;
}) {
  const panel = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    panel.current?.querySelector<HTMLTextAreaElement>("textarea")?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  return (
    <>
      {!open && (
        <button
          type="button"
          onClick={onOpen}
          className="fixed bottom-20 right-4 z-30 inline-flex h-14 items-center gap-2 rounded-full bg-primary pl-4 pr-5 text-label text-on-primary shadow-dialog hover:bg-primary-hover lg:bottom-6 lg:right-6"
        >
          <MessageCircle aria-hidden className="size-5" />
          Ask Sprout
          {unread && <span className="size-2.5 rounded-full bg-sun" aria-label="New message" />}
        </button>
      )}
      <div
        ref={panel}
        role="dialog"
        aria-label="Chat with Sprout"
        aria-hidden={!open}
        inert={!open}
        className={`fixed inset-y-0 right-0 z-40 flex w-full flex-col border-l border-line bg-canvas shadow-dialog transition-transform duration-300 ease-[var(--ease-standard)] sm:w-[440px] ${open ? "translate-x-0" : "translate-x-full"}`}
      >
        <div className="flex items-center gap-3 border-b border-line bg-surface px-4 py-3">
          <Avatar />
          <div className="flex-1">
            <p className="text-label text-ink">Sprout</p>
            <p className="text-caption text-muted">Answers questions. The rules decide; you confirm.</p>
          </div>
          <button type="button" onClick={onClose} aria-label="Close chat" className="inline-flex size-11 items-center justify-center rounded-sm text-ink-2 hover:bg-sunken">
            <X aria-hidden className="size-5" />
          </button>
        </div>
        <div data-scroll-root className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
          {children}
        </div>
        <div className="border-t border-line bg-surface p-3">{composer}</div>
      </div>
    </>
  );
}
