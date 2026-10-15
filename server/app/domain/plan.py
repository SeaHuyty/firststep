"""Deterministic advisory logic. Mock rules for a prototype: not real financial advice.

The AI layer only explains and proposes; every number that reaches the user passes through here.
"""

import math

from .catalog import BUCKET_META
from .schemas import BUCKETS, Pct, Profile


SINGLE_SHARE = 0.2  # default: this share of the stock allocation goes to individual stocks; the client can change it


def js_round(x: float) -> int:
    """Round half up like JavaScript's Math.round (Python's round() is banker's rounding)."""
    return math.floor(x + 0.5)


def allocate_pct(p: Profile) -> Pct:
    """Rules-based default allocation: percent per bucket, sums to 100."""
    emergency = {"none": 30, "insufficient": 20, "enough": 5}[p.emergency] + (5 if p.debt == "significant" else 0)
    rest = 100 - emergency

    base = {1: 0.25, 2: 0.5, 3: 0.7}[p.risk]
    adj = -0.25 if p.horizon == 1 else -0.1 if p.horizon == 3 else 0.1 if p.horizon == 12 else 0
    stock_share = min(0.85, max(0.05, base + adj))

    alt = 5 if p.risk >= 2 and p.horizon >= 7 else 0
    equity = js_round(rest * stock_share)
    single = js_round(equity * SINGLE_SHARE)
    bonds = js_round(max(0, rest - alt - equity) * 0.65)
    cash = 100 - emergency - alt - equity - bonds
    return {"emergency": emergency, "stocks": equity - single, "single": single, "bonds": bonds, "cash": cash, "alt": alt}


def limits(p: Profile) -> dict[str, Pct]:
    """Hard guardrails for any change (AI-proposed or otherwise).

    Stock exposure (fund stocks + individual stocks together) may be at most 15 points above the rules-based
    default and never past a risk cap. At the aggressive level the only cap is the emergency fund, so a client
    who wants extreme risk can put everything else in stocks, split between funds and individual stocks as they
    like. The emergency fund can never drop below the rules-based minimum.
    """
    base = allocate_pct(p)
    cap = {1: 40, 2: 65, 3: 100 - base["emergency"]}[p.risk]
    equity = cap if p.risk == 3 else min(cap, base["stocks"] + base["single"] + 15)
    return {
        "min": {"emergency": base["emergency"], "stocks": 0, "single": 0, "bonds": 0, "cash": 0, "alt": 0},
        "equity": {"max": equity},
        "max": {
            "emergency": 100,
            "stocks": equity,
            "single": equity,
            "bonds": 100,
            "cash": 100,
            "alt": 5 if p.risk == 1 else 10,
        },
    }


def valid_pct(p: Profile, pct: Pct) -> bool:
    lim = limits(p)
    return (
        sum(pct[b] for b in BUCKETS) == 100
        and all(lim["min"][b] <= pct[b] <= lim["max"][b] for b in BUCKETS)
        and pct["stocks"] + pct["single"] <= lim["equity"]["max"]
    )


def apply_targets(p: Profile, current: Pct, targets: dict[str, float]) -> tuple[Pct, list[str]]:
    """Apply requested targets for some buckets.

    Each target is clamped to the guardrails, then the total is rebalanced to 100 using the buckets
    that weren't explicitly targeted first.
    """
    lim = limits(p)
    lo, hi = lim["min"], lim["max"]
    notes: list[str] = []
    nxt = dict(current)
    targeted = [b for b in BUCKETS if targets.get(b) is not None]

    for b in targeted:
        requested = js_round(targets[b])
        nxt[b] = min(hi[b], max(lo[b], requested))
        if nxt[b] != requested:
            notes.append(f"{BUCKET_META[b]['label']} limited to {nxt[b]}% (allowed {lo[b]}–{hi[b]}% for this profile).")

    equity_max = lim["equity"]["max"]
    over = nxt["stocks"] + nxt["single"] - equity_max
    for b in [b for b in ("stocks", "single") if b not in targeted] + [b for b in ("stocks", "single") if b in targeted]:
        cut = max(0, min(over, nxt[b] - lo[b]))
        if cut and b in targeted:
            notes.append(f"{BUCKET_META[b]['label']} limited to {nxt[b] - cut}% (stock exposure is capped at {equity_max}% for this profile).")
        nxt[b] -= cut
        over -= cut

    diff = 100 - sum(nxt[b] for b in BUCKETS)
    stock_order = ["stocks", "single"]
    preferred = ["bonds", "cash", *stock_order, "alt", "emergency"] if diff > 0 else ["cash", "bonds", *stock_order, "alt", "emergency"]
    sequence = [b for b in preferred if b not in targeted] + [b for b in preferred if b in targeted]
    sign = 1 if diff > 0 else -1
    touched: list[str] = []
    for b in sequence:
        if diff == 0:
            break
        room = hi[b] - nxt[b] if sign > 0 else nxt[b] - lo[b]
        if sign > 0 and b in ("stocks", "single"):
            room = min(room, equity_max - nxt["stocks"] - nxt["single"])
        moved = max(0, min(abs(diff), room))
        if moved > 0 and b in targeted:
            touched.append(b)
        nxt[b] += sign * moved
        diff -= sign * moved
    for b in touched:
        notes.append(f"{BUCKET_META[b]['label']} ended at {nxt[b]}% so the total stays 100%.")
    return nxt, notes


def analyse(p: Profile) -> dict:
    emergency_pts = {"none": 0, "insufficient": 15, "enough": 30}[p.emergency]
    debt_pts = {"none": 20, "some": 10, "significant": 0}[p.debt]
    horizon_pts = 10 if p.horizon >= 7 else 5 if p.horizon == 3 else 0
    score = 40 + emergency_pts + debt_pts + horizon_pts

    rows = [
        {
            "label": "Debt level",
            "value": {"none": "Low", "some": "Moderate", "significant": "High"}[p.debt],
            "status": {"none": "good", "some": "ok", "significant": "bad"}[p.debt],
        },
        {
            "label": "Emergency fund",
            "value": {"none": "Missing", "insufficient": "Needs improvement", "enough": "Good"}[p.emergency],
            "status": {"none": "bad", "insufficient": "ok", "enough": "good"}[p.emergency],
        },
        {
            "label": "Time horizon",
            "value": "Long" if p.horizon >= 7 else "Medium" if p.horizon == 3 else "Short",
            "status": "good" if p.horizon >= 7 else "ok" if p.horizon == 3 else "bad",
        },
    ]

    insights: list[str] = []
    if p.emergency != "enough":
        insights.append("Your emergency savings may not cover 6 months of expenses.")
    if p.debt != "none":
        insights.append("Paying down debt first can beat most investment returns.")
    if p.horizon >= 7:
        insights.append("A long horizon allows more growth-oriented investments.")
    else:
        insights.append("A short horizon calls for safer, more liquid holdings.")

    return {"score": score, "rows": rows, "insights": insights}


# Funds suggested per risk level: steadier, broader funds when conservative; higher-growth, more
# volatile ones when aggressive. (group, tickers, reason) per risk.
SUGGESTED: dict[int, list[tuple[str, list[str], str]]] = {
    1: [
        ("Global Stocks (ETF)", ["VT"], "Conservative: one broad worldwide fund spreads risk across thousands of companies."),
        ("Bonds", ["BND", "AGG"], "Conservative: broad investment-grade bond funds for stability and steady income."),
        ("Savings", ["HYSA", "SGOV"], "Conservative: insured, instantly available cash and Treasury bills."),
    ],
    2: [
        ("Global Stocks (ETF)", ["VT", "VOO"], "Moderate: broad worldwide stocks plus U.S. large companies for steady growth."),
        ("Bonds", ["BND"], "Moderate: broad investment-grade bonds as a stabiliser."),
        ("Savings", ["HYSA"], "Moderate: insured, instant access for your safety cushion."),
    ],
    3: [
        ("Global Stocks (ETF)", ["VOO", "QQQM"], "Aggressive: U.S. large companies and the tech-heavy Nasdaq 100 for higher growth, with bigger swings."),
        ("Bonds", ["BND"], "Aggressive: a smaller bond cushion against stock-market drops."),
        ("Savings", ["HYSA"], "Aggressive: insured, instant access for your safety cushion."),
    ],
}


def suggest_picks(risk: int, alt: int) -> dict[str, str]:
    """ticker -> reason for the funds that fit a risk level (plus REITs when the plan has an alternatives slice)."""
    picks = {t: reason for _, tickers, reason in SUGGESTED[risk] for t in tickers}
    if alt > 0:
        picks["VNQ"] = "A small real-estate slice for diversification beyond stocks and bonds."
    return picks


# Annual return assumptions (pessimistic, base, optimistic) per risk level.
RATES: dict[int, tuple[float, float, float]] = {
    1: (0.01, 0.03, 0.05),
    2: (0.0, 0.05, 0.08),
    3: (-0.02, 0.07, 0.11),
}


def project(amount: float, monthly: float, years: int, risk: int) -> list[list[int]]:
    series: list[list[int]] = []
    for annual in RATES[risk]:
        r = annual / 12
        points: list[int] = []
        for y in range(years + 1):
            n = y * 12
            if r == 0:
                fv = amount + monthly * n
            else:
                growth = (1 + r) ** n
                fv = amount * growth + monthly * (growth - 1) / r
            points.append(js_round(fv))
        series.append(points)
    return series
