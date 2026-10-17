"""Check a session's audit log: every link and every hash."""

import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from app.audit.log import GENESIS, event_hash


@dataclass(frozen=True, slots=True)
class ChainCheck:
    """Result of verifying one log."""

    ok: bool
    events: int
    head: str
    first_bad_seq: int | None = None
    reason: str | None = None


def _problem(event: dict[str, Any], seq: int, prev: str) -> str | None:
    """Return what is wrong with one event, or None if it is sound."""
    if event.get("seq") != seq:
        return "sequence number out of order"
    if event.get("prev_hash") != prev:
        return "does not link to the previous event"
    if event_hash(event) != event.get("hash"):
        return "hash does not match the contents"
    return None


def verify_lines(lines: Iterable[str], expected_head: str | None = None) -> ChainCheck:
    """Return whether the lines form an unbroken chain.

    Checks, in order: each line parses, sequence numbers run 0, 1, 2...,
    each event points at the previous hash, and each stored hash matches
    the recomputed one. If expected_head is given (anchored outside the
    file), the final hash must equal it, which catches a rewritten file.
    """
    prev, count = GENESIS, 0
    for line in lines:
        if not line.strip():
            continue
        try:
            problem = _problem(json.loads(line), count, prev)
        except json.JSONDecodeError:
            problem = "line is not valid JSON"
        if problem:
            return ChainCheck(False, count, prev, count, problem)
        prev = json.loads(line)["hash"]
        count += 1
    if expected_head is not None and prev != expected_head:
        return ChainCheck(False, count, prev, None, "latest hash differs from the anchored one")
    return ChainCheck(True, count, prev)
