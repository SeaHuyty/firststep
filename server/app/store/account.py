"""Proposals, used nonces and the paper account."""

import json
import sqlite3
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.core.types import Money, Side


@dataclass(frozen=True, slots=True)
class ProposalRow:
    """A frozen plan waiting for (or past) the user's confirmation."""

    id: str
    session_id: str
    kind: str
    contents: dict[str, Any]
    content_hash: str
    status: str


def save_proposal(  # noqa: PLR0913 (one argument per column)
    con: sqlite3.Connection,
    *,
    proposal_id: str,
    session_id: str,
    kind: str,
    contents: dict[str, Any],
    content_hash: str,
    now: str,
) -> None:
    """Store a new draft and supersede older drafts of the same kind."""
    con.execute(
        "UPDATE proposals SET status = 'superseded'"
        " WHERE session_id = ? AND kind = ? AND status = 'draft'",
        (session_id, kind),
    )
    con.execute(
        "INSERT INTO proposals (id, session_id, kind, contents_json, content_hash, status,"
        " created_at) VALUES (?, ?, ?, ?, ?, 'draft', ?)",
        (proposal_id, session_id, kind, json.dumps(contents, default=str), content_hash, now),
    )


def get_proposal(con: sqlite3.Connection, proposal_id: str) -> ProposalRow | None:
    """Return a proposal, or None."""
    r = con.execute("SELECT * FROM proposals WHERE id = ?", (proposal_id,)).fetchone()
    if r is None:
        return None
    return ProposalRow(
        r["id"],
        r["session_id"],
        r["kind"],
        json.loads(r["contents_json"]),
        r["content_hash"],
        r["status"],
    )


def latest_proposal(con: sqlite3.Connection, session_id: str, kind: str) -> ProposalRow | None:
    """Return the newest live proposal of a kind, or None."""
    r = con.execute(
        "SELECT id FROM proposals WHERE session_id = ? AND kind = ? AND status != 'superseded'"
        " ORDER BY created_at DESC, rowid DESC LIMIT 1",
        (session_id, kind),
    ).fetchone()
    return get_proposal(con, r["id"]) if r else None


def mark_executed(con: sqlite3.Connection, proposal_id: str) -> None:
    """Record that a proposal's orders were placed."""
    con.execute("UPDATE proposals SET status = 'executed' WHERE id = ?", (proposal_id,))


def nonce_used(con: sqlite3.Connection, nonce: str) -> bool:
    """Return whether a confirmation nonce was already spent."""
    return (
        con.execute("SELECT 1 FROM used_nonces WHERE nonce = ?", (nonce,)).fetchone() is not None
    )


def use_nonce(con: sqlite3.Connection, nonce: str, proposal_id: str, now: str) -> None:
    """Spend a nonce; a second use fails on the primary key."""
    con.execute(
        "INSERT INTO used_nonces (nonce, proposal_id, used_at) VALUES (?, ?, ?)",
        (nonce, proposal_id, now),
    )


def cash(con: sqlite3.Connection, session_id: str) -> Money:
    """Return the account's cash balance (zero before any deposit)."""
    r = con.execute("SELECT balance FROM cash WHERE session_id = ?", (session_id,)).fetchone()
    return Decimal(r["balance"]) if r else Decimal(0)


def set_cash(con: sqlite3.Connection, session_id: str, balance: Money) -> None:
    """Set the account's cash balance."""
    con.execute(
        "INSERT INTO cash (session_id, balance) VALUES (?, ?)"
        " ON CONFLICT (session_id) DO UPDATE SET balance = excluded.balance",
        (session_id, str(balance)),
    )


def positions(con: sqlite3.Connection, session_id: str) -> dict[str, Decimal]:
    """Return units held per product."""
    rows = con.execute(
        "SELECT product_id, units FROM positions WHERE session_id = ? ORDER BY product_id",
        (session_id,),
    ).fetchall()
    return {r["product_id"]: Decimal(r["units"]) for r in rows if Decimal(r["units"]) != 0}


def set_units(con: sqlite3.Connection, session_id: str, product_id: str, units: Decimal) -> None:
    """Set units held of one product."""
    con.execute(
        "INSERT INTO positions (session_id, product_id, units) VALUES (?, ?, ?)"
        " ON CONFLICT (session_id, product_id) DO UPDATE SET units = excluded.units",
        (session_id, product_id, str(units)),
    )


@dataclass(frozen=True, slots=True)
class OrderRow:
    """One filled order."""

    id: str
    proposal_id: str | None
    product_id: str
    side: Side
    amount: Money
    units: Decimal
    nav: Decimal
    sim_month: str
    source: str


def add_order(con: sqlite3.Connection, session_id: str, order: OrderRow, now: str) -> None:
    """Record one filled order."""
    con.execute(
        "INSERT INTO orders (id, session_id, proposal_id, product_id, side, amount, units, nav,"
        " sim_month, source, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            order.id,
            session_id,
            order.proposal_id,
            order.product_id,
            order.side,
            str(order.amount),
            str(order.units),
            str(order.nav),
            order.sim_month,
            order.source,
            now,
        ),
    )


def orders(con: sqlite3.Connection, session_id: str) -> list[OrderRow]:
    """Return every order of a session, oldest first."""
    rows = con.execute(
        "SELECT * FROM orders WHERE session_id = ? ORDER BY created_at, id", (session_id,)
    ).fetchall()
    return [
        OrderRow(
            r["id"],
            r["proposal_id"],
            r["product_id"],
            Side(r["side"]),
            Decimal(r["amount"]),
            Decimal(r["units"]),
            Decimal(r["nav"]),
            r["sim_month"],
            r["source"],
        )
        for r in rows
    ]


def auto_invested(con: sqlite3.Connection, session_id: str) -> Money:
    """Return the total bought by the monthly plan so far."""
    rows = con.execute(
        "SELECT amount FROM orders WHERE session_id = ? AND source = 'auto_invest'", (session_id,)
    ).fetchall()
    return sum((Decimal(r["amount"]) for r in rows), Decimal(0))


def spent_on(con: sqlite3.Connection, session_id: str, day: str) -> Money:
    """Return the user's buy total on a calendar day (for LIM-01)."""
    rows = con.execute(
        "SELECT amount FROM orders WHERE session_id = ? AND source = 'user' AND side = 'buy'"
        " AND substr(created_at, 1, 10) = ?",
        (session_id, day),
    ).fetchall()
    return sum((Decimal(r["amount"]) for r in rows), Decimal(0))


@dataclass(frozen=True, slots=True)
class AutoInvestRow:
    """A monthly plan that buys the target mix."""

    monthly: Money
    weights: dict[str, float]
    next_month: str
    active: bool


def set_auto_invest(con: sqlite3.Connection, session_id: str, plan: AutoInvestRow) -> None:
    """Create or replace the session's monthly plan."""
    con.execute(
        "INSERT INTO auto_invest (session_id, monthly, weights_json, next_month, active)"
        " VALUES (?, ?, ?, ?, ?) ON CONFLICT (session_id) DO UPDATE SET"
        " monthly = excluded.monthly, weights_json = excluded.weights_json,"
        " next_month = excluded.next_month, active = excluded.active",
        (
            session_id,
            str(plan.monthly),
            json.dumps(plan.weights),
            plan.next_month,
            int(plan.active),
        ),
    )


def auto_invest(con: sqlite3.Connection, session_id: str) -> AutoInvestRow | None:
    """Return the session's monthly plan, or None."""
    r = con.execute("SELECT * FROM auto_invest WHERE session_id = ?", (session_id,)).fetchone()
    if r is None:
        return None
    return AutoInvestRow(
        Decimal(r["monthly"]), json.loads(r["weights_json"]), r["next_month"], bool(r["active"])
    )


def record_value(con: sqlite3.Connection, session_id: str, month: str, value: Money) -> None:
    """Store the portfolio value at the end of a simulated month."""
    con.execute(
        "INSERT INTO value_history (session_id, sim_month, value) VALUES (?, ?, ?)"
        " ON CONFLICT (session_id, sim_month) DO UPDATE SET value = excluded.value",
        (session_id, month, str(value)),
    )


def value_history(con: sqlite3.Connection, session_id: str) -> list[tuple[str, Money]]:
    """Return (month, value) pairs, oldest first."""
    rows = con.execute(
        "SELECT sim_month, value FROM value_history WHERE session_id = ? ORDER BY sim_month",
        (session_id,),
    ).fetchall()
    return [(r["sim_month"], Decimal(r["value"])) for r in rows]


@dataclass(frozen=True, slots=True)
class CoolingOffRow:
    """A sale waiting out its cooling-off period."""

    id: str
    product_id: str
    amount: Money
    until_hours: float
    status: str


def add_cooling_off(con: sqlite3.Connection, session_id: str, row: CoolingOffRow) -> None:
    """Start a cooling-off period for a sale."""
    con.execute(
        "INSERT INTO cooling_off (id, session_id, product_id, amount, until_hours, status)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (row.id, session_id, row.product_id, str(row.amount), row.until_hours, row.status),
    )


def cooling_offs(
    con: sqlite3.Connection, session_id: str, *, include_released: bool = False
) -> list[CoolingOffRow]:
    """Return waiting (and optionally released) cooling-off periods."""
    statuses = ("waiting", "released") if include_released else ("waiting", "waiting")
    rows = con.execute(
        "SELECT * FROM cooling_off WHERE session_id = ? AND status IN (?, ?)",
        (session_id, *statuses),
    ).fetchall()
    return [
        CoolingOffRow(
            r["id"], r["product_id"], Decimal(r["amount"]), r["until_hours"], r["status"]
        )
        for r in rows
    ]


def set_cooling_off_status(con: sqlite3.Connection, cooling_id: str, status: str) -> None:
    """Release or cancel a waiting sale."""
    con.execute("UPDATE cooling_off SET status = ? WHERE id = ?", (status, cooling_id))
