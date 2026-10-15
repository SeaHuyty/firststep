"use client";

import { useState } from "react";

const DOCS = {
  terms: {
    title: "Terms & Conditions",
    body: [
      "WealthPilot AI is a prototype provided for education and information. By using it you agree to these terms.",
      "The service is provided “as is”, without warranties of any kind. We do not guarantee that it is accurate, complete, current or free of errors, or that it is suitable for your circumstances.",
      "You are solely responsible for your financial decisions. To the fullest extent permitted by law, WealthPilot AI and its contributors are not liable for any loss or damage arising from use of, or reliance on, the service.",
      "We may change or withdraw the service at any time.",
    ],
  },
  privacy: {
    title: "Privacy Policy",
    body: [
      "The details you enter (amount, goals, time horizon, risk tolerance and similar answers) are used to build your plan.",
      "When you chat with the advisor, your messages and a summary of your profile and plan are sent to a third-party AI provider to generate replies. Market data comes from third-party sources such as Yahoo Finance.",
      "Do not enter personal identifiers, account numbers or other sensitive information. We do not sell your data.",
    ],
  },
  disclaimer: {
    title: "Disclaimer",
    body: [
      "For education and information only. Nothing here is financial, investment, tax or legal advice, or an offer or recommendation to buy or sell any security.",
      "WealthPilot AI is not a licensed financial adviser, broker or fund manager. Allocations, product lists and projections come from simplified rules and assumptions, not from a review of your full situation.",
      "Past performance does not predict future results. Projections are illustrations, not promises. Investing involves risk, including the loss of the money you invest.",
      "Talk to a qualified, licensed professional before making investment decisions.",
    ],
  },
  risk: {
    title: "Risk Disclosure",
    body: [
      "All investments can lose value. Stocks, funds, bonds and real estate can fall sharply, and individual stocks are usually riskier than diversified funds.",
      "A portfolio weighted toward individual stocks can lose a large part of its value, especially over short periods.",
      "AI can make mistakes. Replies may be wrong, incomplete or out of date, so check anything important against official sources.",
      "Invest only money you can afford to lose, and invest at your own risk.",
    ],
  },
} as const;

type DocKey = keyof typeof DOCS;

export function Footer() {
  const [open, setOpen] = useState<DocKey | null>(null);
  const doc = open ? DOCS[open] : null;

  return (
    <footer className="bg-blue-600 px-5 py-8 md:px-12">
      <div className="mx-auto max-w-5xl">
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div>
            <p className="font-semibold text-white">WealthPilot AI</p>
            <p className="text-xs text-blue-100">Your money, smarter future</p>
          </div>
          <nav className="flex flex-wrap gap-x-5 gap-y-2 text-sm text-blue-50" aria-label="Legal">
            {(Object.keys(DOCS) as DocKey[]).map((k) => (
              <button key={k} onClick={() => setOpen(k)} className="hover:text-white hover:underline">
                {DOCS[k].title}
              </button>
            ))}
          </nav>
        </div>

        <p className="mt-6 text-xs leading-relaxed text-white">
          <strong>Important:</strong> WealthPilot AI is for education and information only and is not financial advice.
          Investing involves risk, including loss of the money you invest. Past performance does not guarantee future
          results. AI can make mistakes. Invest at your own risk, and consult a licensed professional before you act.
        </p>
        <p className="mt-4 text-xs text-blue-100">© {new Date().getFullYear()} WealthPilot AI. All rights reserved.</p>
      </div>

      {doc && (
        <div
          className="fixed inset-0 z-30 flex items-center justify-center bg-slate-900/40 p-4"
          onClick={() => setOpen(null)}
          role="dialog"
          aria-modal="true"
          aria-label={doc.title}
        >
          <div className="max-h-[80vh] w-full max-w-lg overflow-y-auto rounded-xl bg-white p-6 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-start justify-between gap-4">
              <h2 className="text-lg font-semibold text-slate-900">{doc.title}</h2>
              <button onClick={() => setOpen(null)} className="text-slate-500 hover:text-slate-900" aria-label="Close">
                ✕
              </button>
            </div>
            <div className="mt-3 space-y-3 text-sm leading-relaxed text-slate-600">
              {doc.body.map((t) => (
                <p key={t}>{t}</p>
              ))}
            </div>
          </div>
        </div>
      )}
    </footer>
  );
}
