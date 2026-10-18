"""Draw the Results figure (docs/results.svg) from the evidence files.

    python scripts/results_figure.py     # after metrics.py

Numbers come only from evidence/metrics.json and evidence/redteam.json.
Colours are the FirstStep brand green for the guardian plus two
categorical slots, checked for colour-blind separation in this order
(orange, blue, green), so stacked neighbours stay distinguishable.
"""

import json
from collections import Counter
from html import escape
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
EVIDENCE = SERVER_DIR / "evidence"
OUT = SERVER_DIR.parent / "docs" / "results.svg"

BG, INK, INK_2, MUTED, LINE = "#F6F8F7", "#0C1F22", "#3F5457", "#5A6C6E", "#DDE5E3"
# How an attack was stopped, in stacking order (blue always sits between).
LAYERS = [
    ("guard", "Input guard", "flagged or masked before the LLM", "#eb6834"),
    ("declined", "No tool called", "Sprout answered, nothing ran", "#2a78d6"),
    ("rule", "Guardian rule", "refused with a rule ID", "#0A7D55"),
]
CATEGORY = {
    "injection": "Prompt injection",
    "suitability": "Unsuitable funds",
    "agency": "Acting without a click",
    "readiness": "Investing before ready",
    "language": "Promises, predictions",
    "cooling_off": "Panic selling",
    "privacy": "Personal data",
    "limits": "Order limits",
    "scope": "Out of scope",
}


def _layer(notes: list[str]) -> str:
    text = " ".join(notes)
    if "guard:" in text:
        return "guard"
    return "rule" if "refused" in text else "declined"


def _text(x: float, y: float, s: str, size: int, fill: str, **attrs: str) -> str:
    extra = "".join(f' {k.replace("_", "-")}="{v}"' for k, v in attrs.items())
    return f'<text x="{x:g}" y="{y:g}" font-size="{size}" fill="{fill}"{extra}>{escape(s)}</text>'


def _tile(x: int, value: str, label: str, note: str) -> list[str]:
    return [
        f'<rect x="{x}" y="104" width="270" height="112" rx="12" fill="#FFFFFF" stroke="{LINE}"/>',
        _text(x + 20, 158, value, 40, INK, font_weight="600"),
        _text(x + 20, 184, label, 14, INK),
        _text(x + 20, 203, note, 12, MUTED),
    ]


def _bar_end(x: float, y: float, w: float, h: float, fill: str) -> str:
    """A segment whose right end is rounded (4px), anchored at the left."""
    r = min(4.0, w / 2)
    return (
        f'<path d="M{x:g} {y:g} H{x + w - r:g} Q{x + w:g} {y:g} {x + w:g} {y + r:g} '
        f'V{y + h - r:g} Q{x + w:g} {y + h:g} {x + w - r:g} {y + h:g} H{x:g} Z" fill="{fill}"/>'
    )


def build(metrics: dict, redteam: dict) -> str:
    counts: dict[str, Counter[str]] = {}
    for r in redteam["results"]:
        counts.setdefault(r["category"], Counter())[_layer(r.get("notes") or [])] += 1
    rows = sorted(
        counts.items(), key=lambda kv: (-sum(kv[1].values()), list(CATEGORY).index(kv[0]))
    )
    totals = Counter[str]()
    for _, c in rows:
        totals.update(c)

    model = "scripted" if metrics["llm"] == "fake" else metrics["llm"]
    out = [
        '<rect width="1200" height="650" fill="' + BG + '"/>',
        _text(
            30,
            42,
            "Results: every attack stopped, every step on record",
            22,
            INK,
            font_weight="600",
        ),
        _text(
            30,
            66,
            f"From the evidence run: {redteam['total']} red-team attacks and the demo people, "
            f"on the {model} model. A real-model run is still to come.",
            13,
            INK_2,
        ),
    ]
    fills = metrics["orders_filled"]
    out += _tile(
        30,
        f"{redteam['passed']} / {redteam['total']}",
        "red-team attacks handled safely",
        "nothing filled, chain intact",
    )
    out += _tile(320, str(fills), "orders filled", "every one after a Confirm click")
    out += _tile(
        610,
        f"{metrics['chains_verified']} / {metrics['audit_logs']}",
        "audit chains verified",
        f"{metrics['audit_events']} events, none altered",
    )
    out += _tile(
        900,
        str(metrics["tests_passed"]),
        "automated tests passing",
        f"{metrics['coverage_pct']:g}% line coverage",
    )

    # The chart: attacks by category, stacked by the layer that stopped them.
    top, row_h, bar_h, x0, unit = 300, 34, 20, 230, 100
    out.append(_text(30, 262, "How each attack was stopped", 16, INK, font_weight="600"))
    out.append(
        _text(
            30,
            282,
            "Attacks by category; each bar is split by the layer that stopped it.",
            12,
            MUTED,
        )
    )
    for i, (cat, c) in enumerate(rows):
        y = top + i * row_h
        out.append(_text(x0 - 12, y + 15, CATEGORY.get(cat, cat), 13, INK_2, text_anchor="end"))
        x = float(x0)
        present = [layer for layer in LAYERS if c[layer[0]]]
        for j, (key, _, _, color) in enumerate(present):
            w = c[key] * unit
            gap = 2 if j < len(present) - 1 else 0  # a 2px surface gap between fills
            if j == len(present) - 1:
                out.append(_bar_end(x, y, w, bar_h, color))
            else:
                out.append(
                    f'<rect x="{x:g}" y="{y}" width="{w - gap:g}" height="{bar_h}" fill="{color}"/>'
                )
            x += w
        out.append(_text(x + 8, y + 15, str(sum(c.values())), 13, INK, font_weight="600"))
    axis_y = top + len(rows) * row_h - 6
    out.append(
        f'<line x1="{x0}" y1="{top - 8}" x2="{x0}" y2="{axis_y}" stroke="{MUTED}" stroke-width="1"/>'
    )

    # Legend with each layer's total: identity is never colour alone.
    lx, ly = 900, 300
    out.append(_text(lx, ly - 2, "Stopped by", 12, MUTED, font_weight="600", letter_spacing="1"))
    for k, (key, name, note, color) in enumerate(LAYERS):
        y = ly + 22 + k * 64
        out.append(f'<rect x="{lx}" y="{y - 12}" width="14" height="14" rx="3" fill="{color}"/>')
        out.append(_text(lx + 24, y, f"{name}: {totals[key]}", 15, INK, font_weight="600"))
        out.append(_text(lx + 24, y + 20, note, 12, INK_2))
    out.append(_text(lx, ly + 22 + 3 * 64, "Every case also checks: no fill, no", 12, MUTED))
    out.append(_text(lx, ly + 40 + 3 * 64, "token logged, chain verified.", 12, MUTED))

    label = (
        f"FirstStep results: {redteam['passed']} of {redteam['total']} red-team attacks handled "
        f"safely ({totals['guard']} by the input guard, {totals['rule']} by a guardian rule, "
        f"{totals['declined']} answered with no tool called); {fills} orders filled, each after "
        f"a Confirm click; {metrics['chains_verified']} of {metrics['audit_logs']} audit chains "
        f"verified; {metrics['tests_passed']} tests passing."
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 650" width="1200" '
        f'height="650" role="img" aria-label="{escape(label)}" '
        'font-family="IBM Plex Sans, Helvetica, Arial, sans-serif">\n'
        + "\n".join(f"  {line}" for line in out)
        + "\n</svg>\n"
    )


def main() -> None:
    metrics = json.loads((EVIDENCE / "metrics.json").read_text(encoding="utf-8"))
    redteam = json.loads((EVIDENCE / "redteam.json").read_text(encoding="utf-8"))
    OUT.write_text(build(metrics, redteam), encoding="utf-8")
    print(f"wrote {OUT.relative_to(SERVER_DIR.parent)}")


if __name__ == "__main__":
    main()
