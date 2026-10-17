import json
import threading
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.audit.log import GENESIS, AuditLog
from app.audit.verify import verify_lines

FIXED = datetime(2026, 10, 17, 9, 30, tzinfo=UTC)


@pytest.fixture
def log(tmp_path: Path) -> AuditLog:
    return AuditLog(tmp_path / "s1.jsonl", "s1", clock=lambda: FIXED)


def lines(log: AuditLog) -> list[str]:
    return log.path.read_text().splitlines()


def write_three(log: AuditLog) -> None:
    log.append("user_msg", "user", {"text": "hello"})
    log.append("tool_call", "llm", {"tool": "assess_readiness", "args": {}})
    log.append("policy", "system", {"rule_id": "READY-01", "allowed": False})


def test_events_chain_from_genesis(log: AuditLog) -> None:
    assert log.head() == GENESIS
    write_three(log)
    events = list(log.events())
    assert [e.seq for e in events] == [0, 1, 2]
    assert events[0].prev_hash == GENESIS
    assert events[1].prev_hash == events[0].hash
    assert log.head() == events[2].hash


def test_untouched_log_verifies(log: AuditLog) -> None:
    write_three(log)
    result = verify_lines(lines(log), expected_head=log.head())
    assert result.ok
    assert result.events == 3


def test_empty_log_verifies() -> None:
    assert verify_lines([]).ok


def test_edited_payload_is_caught(log: AuditLog) -> None:
    write_three(log)
    rows = lines(log)
    event = json.loads(rows[2])
    event["payload"]["allowed"] = True  # someone flips a refusal into an approval
    rows[2] = json.dumps(event)
    result = verify_lines(rows)
    assert not result.ok
    assert result.first_bad_seq == 2
    assert result.reason == "hash does not match the contents"


def test_deleted_line_is_caught(log: AuditLog) -> None:
    write_three(log)
    rows = lines(log)
    result = verify_lines([rows[0], rows[2]])
    assert not result.ok
    assert result.first_bad_seq == 1


def test_reordered_lines_are_caught(log: AuditLog) -> None:
    write_three(log)
    rows = lines(log)
    assert not verify_lines([rows[1], rows[0], rows[2]]).ok


def test_broken_json_is_caught(log: AuditLog) -> None:
    write_three(log)
    rows = lines(log)
    result = verify_lines([rows[0], "{not json"])
    assert result.reason == "line is not valid JSON"


def test_forged_link_with_rehashed_event_is_caught(log: AuditLog) -> None:
    write_three(log)
    rows = lines(log)
    event = json.loads(rows[1])
    event["prev_hash"] = "f" * 64
    rows[1] = json.dumps(event)
    assert verify_lines(rows).reason == "does not link to the previous event"


def test_a_fully_rewritten_file_is_caught_by_the_anchor(log: AuditLog, tmp_path: Path) -> None:
    write_three(log)
    anchored = log.head()
    forged = AuditLog(tmp_path / "forged.jsonl", "s1", clock=lambda: FIXED)
    forged.append("user_msg", "user", {"text": "something else"})
    rows = lines(forged)
    assert verify_lines(rows).ok  # a rewritten chain is internally consistent...
    result = verify_lines(rows, expected_head=anchored)
    assert not result.ok  # ...but no longer matches the hash anchored outside the file
    assert result.reason == "latest hash differs from the anchored one"


def test_reopening_continues_the_chain(log: AuditLog) -> None:
    write_three(log)
    again = AuditLog(log.path, "s1", clock=lambda: FIXED)
    again.append("reply", "llm", {"text": "ok"})
    assert verify_lines(lines(again)).ok
    assert [e.seq for e in again.events()][-1] == 3


def test_parallel_appends_keep_the_chain_intact(log: AuditLog) -> None:
    def work() -> None:
        for i in range(20):
            log.append("system", "system", {"i": i})

    threads = [threading.Thread(target=work) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    result = verify_lines(lines(log))
    assert result.ok
    assert result.events == 80
