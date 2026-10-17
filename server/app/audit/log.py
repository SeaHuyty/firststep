"""Append-only, hash-chained audit log: one JSONL file per session.

Every event stores the SHA-256 of the previous event, so editing,
deleting or reordering a line breaks the chain (`app.audit.verify`).
This follows the chained-record idea of Schneier and Kelsey's secure
audit logs. A plain hash chain cannot stop someone who rewrites the
whole file, so the latest hash is also anchored outside the file (in
the sandbox database and on every order receipt). See
docs/methodology.md and the security self-assessment.
"""

import hashlib
import json
import threading
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, JsonValue

GENESIS = "0" * 64

EventType = Literal[
    "user_msg", "guard", "tool_call", "policy", "tool_result", "fill", "reply", "system"
]
Actor = Literal["user", "llm", "system"]


class AuditEvent(BaseModel):
    """One line of the audit log."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ts: str
    session: str
    seq: int
    type: EventType
    actor: Actor
    payload: dict[str, JsonValue]
    prev_hash: str
    hash: str


def canonical(fields: dict[str, object]) -> bytes:
    """Return the exact bytes that are hashed: sorted, compact JSON."""
    return json.dumps(fields, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def event_hash(event: AuditEvent | dict[str, object]) -> str:
    """Return the SHA-256 of an event's fields, except its own hash."""
    fields = event.model_dump() if isinstance(event, AuditEvent) else dict(event)
    fields.pop("hash", None)
    return hashlib.sha256(canonical(fields)).hexdigest()


def utc_now() -> datetime:
    """Return the current time in UTC."""
    return datetime.now(UTC)


class AuditLog:
    """Writer for one session's log file. Safe across threads."""

    # One lock and one cached tail (seq, hash) per file, shared by every
    # writer in the process, so appends never re-read the whole file.
    _locks: dict[Path, threading.Lock] = {}  # noqa: RUF012
    _tails: dict[Path, tuple[int, str]] = {}  # noqa: RUF012
    _locks_guard = threading.Lock()

    def __init__(self, path: Path, session: str, clock: Callable[[], datetime] = utc_now) -> None:
        """Open (or create) the log at path for a session."""
        self.path = path
        self.session = session
        self._clock = clock
        self._key = path.resolve()
        with AuditLog._locks_guard:
            self._lock = AuditLog._locks.setdefault(self._key, threading.Lock())

    def events(self) -> Iterator[AuditEvent]:
        """Yield every event in file order."""
        if not self.path.exists():
            return
        with self.path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    yield AuditEvent.model_validate_json(line)

    def _tail(self) -> tuple[int, str]:
        """Return (next seq, previous hash), reading the file once."""
        if self._key not in AuditLog._tails:
            last = None
            for last in self.events():  # noqa: B007 (we want the final one)
                pass
            AuditLog._tails[self._key] = (last.seq + 1, last.hash) if last else (0, GENESIS)
        return AuditLog._tails[self._key]

    def head(self) -> str:
        """Return the latest event's hash, or GENESIS when empty."""
        with self._lock:
            return self._tail()[1]

    def append(self, type_: EventType, actor: Actor, payload: dict[str, JsonValue]) -> AuditEvent:
        """Append one event chained to the previous one; return it."""
        with self._lock:
            seq, prev_hash = self._tail()
            fields: dict[str, object] = {
                "ts": self._clock().isoformat(timespec="milliseconds"),
                "session": self.session,
                "seq": seq,
                "type": type_,
                "actor": actor,
                "payload": payload,
                "prev_hash": prev_hash,
            }
            event = AuditEvent.model_validate({**fields, "hash": event_hash(fields)})
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(event.model_dump_json() + "\n")
            AuditLog._tails[self._key] = (seq + 1, event.hash)
            return event
