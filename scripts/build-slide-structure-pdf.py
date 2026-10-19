#!/usr/bin/env python3
"""Render the FirstStep presentation slide structure to docs/pdf/slide-structure.pdf.

Uses reportlab only (no pandoc / browser needed). Styling mirrors the repo's
FirstStep green palette from scripts/docs-pdf.css.
"""
from __future__ import annotations

from pathlib import Path

from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    HRFlowable,
    ListFlowable,
    ListItem,
    KeepTogether,
)

GREEN = HexColor("#0A7D55")
INK = HexColor("#0C1F22")
MUTED = HexColor("#5A6C6E")
RULE = HexColor("#DDE5E3")

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "pdf" / "slide-structure.pdf"


def make_styles():
    base = getSampleStyleSheet()
    styles = {}
    styles["title"] = ParagraphStyle(
        "title", parent=base["Title"], fontName="Helvetica-Bold",
        fontSize=22, leading=26, textColor=GREEN, spaceAfter=4,
    )
    styles["subtitle"] = ParagraphStyle(
        "subtitle", parent=base["Normal"], fontName="Helvetica",
        fontSize=11, leading=15, textColor=MUTED, spaceAfter=10,
    )
    styles["section"] = ParagraphStyle(
        "section", parent=base["Heading2"], fontName="Helvetica-Bold",
        fontSize=14, leading=18, textColor=GREEN, spaceBefore=14, spaceAfter=4,
    )
    styles["slide"] = ParagraphStyle(
        "slide", parent=base["Heading3"], fontName="Helvetica-Bold",
        fontSize=11.5, leading=15, textColor=INK, spaceBefore=10, spaceAfter=2,
    )
    styles["body"] = ParagraphStyle(
        "body", parent=base["Normal"], fontName="Helvetica",
        fontSize=10, leading=14, textColor=INK, alignment=TA_LEFT, spaceAfter=2,
    )
    styles["bullet"] = ParagraphStyle(
        "bullet", parent=styles["body"], leftIndent=6, spaceAfter=1,
    )
    styles["note"] = ParagraphStyle(
        "note", parent=styles["body"], fontSize=9, textColor=MUTED, spaceAfter=2,
    )
    return styles


def bullets(items, style, bullet_style):
    return ListFlowable(
        [ListItem(Paragraph(t, bullet_style), leftIndent=10, value="\u2022") for t in items],
        bulletType="bullet",
        bulletColor=GREEN,
        start="bullet",
        leftIndent=12,
    )


def build():
    S = make_styles()
    story = []

    story.append(Paragraph("FirstStep &mdash; Presentation Slide Structure", S["title"]))
    story.append(Paragraph(
        "Slide plan for the 10-minute pitch, derived from "
        "<i>docs/technical-documentation.md</i>. "
        "2026 Shenzhen FinTechathon &middot; International Track &middot; Topic B: Wealth Advisory Agent.",
        S["subtitle"],
    ))
    story.append(Paragraph(
        "Target: ~10 min &middot; 16 slides (~30&ndash;40s each) &middot; "
        "Audience: FinTechathon judges. "
        "Narrative arc: Problem (1&ndash;3) &rarr; Product (4&ndash;6) &rarr; "
        "Mechanism (7&ndash;11) &rarr; Evidence (12&ndash;16).",
        S["note"],
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=RULE, spaceBefore=6, spaceAfter=4))

    sections = [
        ("Section A &mdash; Hook & Problem (slides 1&ndash;3)", [
            ("Slide 1 &mdash; Title", [
                "Project name <b>FirstStep</b>; tagline: &ldquo;A trustworthy first advisor for first-time investors.&rdquo;",
                "Meet <b>Sprout</b>, the guide.",
                "Competition line: 2026 Shenzhen FinTechathon &middot; International Track &middot; Topic B.",
                "Footer disclaimer: <i>Educational simulation. Not financial advice. No real money moves.</i>",
                "Team names / repository URL.",
            ]),
            ("Slide 2 &mdash; The Problem", [
                "First-time investors rarely fail by picking the wrong fund. They fail by:",
                "&ndash; Investing money they&rsquo;ll need soon",
                "&ndash; Carrying expensive debt",
                "&ndash; Buying products riskier than they can bear",
                "&ndash; Selling in the first crash",
                "The twist: an LLM advisor makes this <i>worse</i> if it can be talked into anything &mdash; promising returns, recommending unsuitable products, placing unapproved orders.",
            ]),
            ("Slide 3 &mdash; Our Thesis (the one big idea)", [
                "<b>&ldquo;The LLM talks; a deterministic guardian decides.&rdquo;</b>",
                "The model chooses words and which tool to call. Every number, product and order comes from tested Python.",
                "Buying needs a one-time token that only the user&rsquo;s Confirm click creates &mdash; the model never sees it.",
                "<i>This is the slide the whole deck hangs on.</i>",
            ]),
        ]),
        ("Section B &mdash; What It Does (slides 4&ndash;6)", [
            ("Slide 4 &mdash; The Advisory Journey", [
                "The closed loop, each step a logged tool call:",
                "1. Money check (readiness) &nbsp; 2. Risk level C1&ndash;C5 &nbsp; 3. Product comparison in plain words",
                "4. A plan (range of outcomes, never one number) &nbsp; 5. Orders you confirm &nbsp; 6. Monitoring through real history",
                "Visual: stage flow diagram.",
            ]),
            ("Slide 5 &mdash; Three Demo People", [
                "<b>Amina</b> (21, credit-card debt): Sprout says &ldquo;not yet&rdquo; &rarr; savings plan.",
                "<b>Leo</b> (27, balanced C3): builds a plan, confirms orders, lives through March 2020.",
                "<b>Mei</b> (58, careful C2): asks for all tech stocks &rarr; refused in plain words.",
                "Visual: phone-amina-not-yet.png, desktop-leo-plan.png, desktop-mei-refusal.png.",
            ]),
            ("Slide 6 &mdash; Live Demo / Screenshots", [
                "One question per page &rarr; dashboard (Home, Plan, Funds, Activity).",
                "A refusal card: names the rule, says why, offers a next step.",
                "Confirm dialog: every trade waits for your click.",
                "Visual: desktop-leo-confirm.png + desktop-mei-refusal.png.",
            ]),
        ]),
        ("Section C &mdash; How It Works (slides 7&ndash;11)", [
            ("Slide 7 &mdash; System Architecture", [
                "Three ways in (tap, typed message, Confirm click) &rarr; <b>one executor</b>.",
                "Layered design: api &rarr; agent &rarr; policy &rarr; tools &rarr; engine (pure engine), enforced by import-linter.",
                "Visual: architecture.png.",
            ]),
            ("Slide 8 &mdash; One Path for Every Action", [
                "Every call: validate args &rarr; <b>guardian check</b> &rarr; run tool &rarr; log to hash-chained audit.",
                "A refusal comes back as data (rule ID + plain message), never an exception.",
                "Model never sees: a number it didn&rsquo;t get from a tool, the place_order tool, or a confirmation token.",
            ]),
            ("Slide 9 &mdash; The Two Roles & Tool Tiers", [
                "Advisor (LLM): reads, picks tools, writes words &mdash; forbidden to guarantee or predict.",
                "Guardian (code): re-checks every call regardless of what the model asked.",
                "Tool tiers: 0 Read &middot; 1 Propose &middot; 2 Execute (never offered to LLM) &middot; 3 Sensitive (cooling-off).",
            ]),
            ("Slide 10 &mdash; Core Algorithms (the finance)", [
                "Readiness: 3-month fund, no debt &gt; 8% APR.",
                "Risk C1&ndash;C5: tolerance vs capacity, <b>lower wins</b> (Grable &amp; Lytton; CSRC suitability).",
                "Allocation: model portfolios, concentration caps (&le;40%/fund).",
                "<b>Range of outcomes:</b> moving-block bootstrap, 5,000 paths, 10th/50th/90th percentile &mdash; never one number.",
                "Worked example: Leo &rarr; ~$59,500 typical (bad $47,300 / good $72,100).",
            ]),
            ("Slide 11 &mdash; Security: Defence in Depth", [
                "Layers: input guard &rarr; stage-scoped tools &rarr; guardian &rarr; <b>HMAC confirm token (CONF-01)</b> &rarr; output filter &rarr; cooling-off &rarr; hash-chained audit.",
                "Maps to OWASP Top 10 for LLM Apps 2025 (LLM01 Prompt Injection, LLM06 Excessive Agency).",
                "<b>Key property: no defence depends on the model behaving.</b>",
            ]),
        ]),
        ("Section D &mdash; Proof & Close (slides 12&ndash;16)", [
            ("Slide 12 &mdash; Results (headline numbers)", [
                "25 / 25 typed requests completed.",
                "<b>30 / 30 red-team attacks handled safely</b> &mdash; nothing filled without a Confirm click.",
                "4 / 4 audit hash chains verified.",
                "223 tests passing &middot; 95% line coverage.",
                "Measured on Gemma 4 26B, open-weight, free tier &mdash; judged from the audit log, not the wording.",
                "Visual: results.png.",
            ]),
            ("Slide 13 &mdash; How We Tested", [
                "Task completion (25), Red team (30 attacks / 9 categories), Personas (3 end-to-end), 223 automated + Playwright E2E.",
                "Everything judged from the audit log; CI runs on every push.",
            ]),
            ("Slide 14 &mdash; Honesty & Limits", [
                "Funds fictional; returns are <i>real</i> monthly history 2000&ndash;2025 (French Library, FRED, World Bank).",
                "Outcomes are ranges from history, not forecasts &mdash; never called a backtest.",
                "Known limits: simplified questionnaire, no real KYC, single currency, LLM can still word things badly (output filter mitigates).",
            ]),
            ("Slide 15 &mdash; Why It Matters / Differentiation", [
                "Open-weight model &rarr; a bank could self-host and keep client data in-house.",
                "Compliance edits a number in rules.yaml, not in code.",
                "Works fully offline on a scripted model &mdash; demo/tests/CI never depend on a network.",
            ]),
            ("Slide 16 &mdash; Close", [
                "Recap the thesis: <i>the LLM talks, the guardian decides.</i>",
                "Repo URL &middot; live demo link &middot; &ldquo;Every trade waits for your click.&rdquo;",
                "Thank you / Q&amp;A.",
            ]),
        ]),
    ]

    for sec_title, slides in sections:
        story.append(Paragraph(sec_title, S["section"]))
        for slide_title, items in slides:
            block = [Paragraph(slide_title, S["slide"]), bullets(items, S["body"], S["bullet"])]
            story.append(KeepTogether(block))

    story.append(HRFlowable(width="100%", thickness=1, color=RULE, spaceBefore=12, spaceAfter=6))
    story.append(Paragraph("Design notes", S["section"]))
    story.append(bullets([
        "Strict 10 min: merge 8&rarr;7 and 13&rarr;12. Longer slot: split slide 10 into two.",
        "Visual assets in repo: docs/images/architecture.png, results.png, and 11 screenshots under docs/images/screenshots/.",
        "Existing deck: docs/slides/presentation.html; speaker notes: docs/presentation-notes.md &mdash; keep this structure consistent with them.",
    ], S["body"], S["bullet"]))

    doc = BaseDocTemplate(
        str(OUT), pagesize=A4,
        leftMargin=16 * mm, rightMargin=16 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
        title="FirstStep - Slide Structure",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")

    def footer(canvas, _doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(MUTED)
        canvas.drawCentredString(
            A4[0] / 2, 10 * mm,
            f"FirstStep \u00b7 Slide Structure \u00b7 {_doc.page}",
        )
        canvas.restoreState()

    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=footer)])
    doc.build(story)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    build()
