"""Sessions and their chat messages."""

import json
import sqlite3
from dataclasses import dataclass
from typing import Any

from app.core.profile import Profile
from app.core.types import Stage


@dataclass(frozen=True, slots=True)
class SessionRow:
    """One client session."""

    id: str
    persona: str | None
    stage: Stage
    profile: Profile
    sim_month: str
    sim_offset_hours: float
    audit_head: str


@dataclass(frozen=True, slots=True)
class MessageRow:
    """One chat message with the cards shown under it."""

    role: str
    text: str
    cards: list[dict[str, Any]]


def create(  # noqa: PLR0913 (one argument per column)
    con: sqlite3.Connection,
    *,
    session_id: str,
    persona: str | None,
    stage: Stage,
    sim_month: str,
    audit_head: str,
    now: str,
) -> None:
    """Insert a new session with an empty profile."""
    con.execute(
        "INSERT INTO sessions (id, persona, stage, profile_json, sim_month, audit_head,"
        " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (session_id, persona, stage, Profile().model_dump_json(), sim_month, audit_head, now, now),
    )


def get(con: sqlite3.Connection, session_id: str) -> SessionRow | None:
    """Return a session, or None if there is no such id."""
    row = con.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if row is None:
        return None
    return SessionRow(
        id=row["id"],
        persona=row["persona"],
        stage=Stage(row["stage"]),
        profile=Profile.model_validate_json(row["profile_json"]),
        sim_month=row["sim_month"],
        sim_offset_hours=row["sim_offset_hours"],
        audit_head=row["audit_head"],
    )


def update(  # noqa: PLR0913 (any subset of the mutable columns)
    con: sqlite3.Connection,
    session_id: str,
    *,
    now: str,
    stage: Stage | None = None,
    profile: Profile | None = None,
    sim_month: str | None = None,
    sim_offset_hours: float | None = None,
    audit_head: str | None = None,
) -> None:
    """Update the given columns of a session."""
    changes: dict[str, object] = {
        "stage": stage,
        "profile_json": profile.model_dump_json() if profile else None,
        "sim_month": sim_month,
        "sim_offset_hours": sim_offset_hours,
        "audit_head": audit_head,
    }
    sets = {k: v for k, v in changes.items() if v is not None}
    sets["updated_at"] = now
    # Column names come from the fixed dict above, never from input.
    columns = ", ".join(f"{k} = ?" for k in sets)
    con.execute(f"UPDATE sessions SET {columns} WHERE id = ?", (*sets.values(), session_id))  # noqa: S608


def add_message(
    con: sqlite3.Connection,
    session_id: str,
    role: str,
    text: str,
    cards: list[dict[str, Any]],
    now: str,
) -> None:
    """Append one chat message."""
    con.execute(
        "INSERT INTO messages (session_id, role, text, cards_json, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (session_id, role, text, json.dumps(cards), now),
    )


def messages(con: sqlite3.Connection, session_id: str, limit: int = 200) -> list[MessageRow]:
    """Return the latest messages of a session, oldest first."""
    rows = con.execute(
        "SELECT role, text, cards_json FROM messages WHERE session_id = ?"
        " ORDER BY id DESC LIMIT ?",
        (session_id, limit),
    ).fetchall()
    return [MessageRow(r["role"], r["text"], json.loads(r["cards_json"])) for r in reversed(rows)]
