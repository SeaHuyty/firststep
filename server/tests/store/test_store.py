import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest

from app.core.profile import Profile
from app.core.types import Side, Stage
from app.store import account, sessions
from app.store.db import Store

NOW = "2026-10-17T10:00:00+00:00"
D = Decimal


@pytest.fixture
def store(tmp_path: Path) -> Store:
    s = Store(tmp_path / "sandbox.db")
    with s.tx() as con:
        sessions.create(
            con,
            session_id="s1",
            persona="leo",
            stage=Stage.ONBOARD,
            sim_month="2019-10",
            audit_head="0" * 64,
            now=NOW,
        )
    return s


def test_new_session_has_an_empty_profile(store: Store) -> None:
    with store.tx() as con:
        row = sessions.get(con, "s1")
    assert row is not None
    assert row.stage == Stage.ONBOARD
    assert row.profile == Profile()
    assert sessions.get(store._connect(), "nope") is None


def test_update_changes_only_given_columns(store: Store) -> None:
    with store.tx() as con:
        sessions.update(con, "s1", now=NOW, stage=Stage.READINESS, profile=Profile(age=27))
    with store.tx() as con:
        row = sessions.get(con, "s1")
    assert row is not None
    assert (row.stage, row.profile.age, row.sim_month) == (Stage.READINESS, 27, "2019-10")


def update_then_fail(store: Store) -> None:
    with store.tx() as con:
        sessions.update(con, "s1", now=NOW, stage=Stage.MONITOR)
        raise RuntimeError("boom")


def test_a_failed_transaction_rolls_back(store: Store) -> None:
    with pytest.raises(RuntimeError):
        update_then_fail(store)
    with store.tx() as con:
        row = sessions.get(con, "s1")
    assert row is not None
    assert row.stage == Stage.ONBOARD


def test_messages_come_back_in_order(store: Store) -> None:
    with store.tx() as con:
        sessions.add_message(con, "s1", "user", "hi", [], NOW)
        sessions.add_message(con, "s1", "sprout", "hello", [{"type": "question"}], NOW)
    with store.tx() as con:
        rows = sessions.messages(con, "s1")
    assert [(m.role, m.text, m.cards) for m in rows] == [
        ("user", "hi", []),
        ("sprout", "hello", [{"type": "question"}]),
    ]


def test_new_draft_supersedes_the_old_one(store: Store) -> None:
    with store.tx() as con:
        for pid in ("p1", "p2"):
            account.save_proposal(
                con,
                proposal_id=pid,
                session_id="s1",
                kind="orders",
                contents={"x": pid},
                content_hash="h",
                now=NOW,
            )
        account.mark_executed(con, "p2")
    with store.tx() as con:
        p1, p2 = account.get_proposal(con, "p1"), account.get_proposal(con, "p2")
    assert p1 is not None
    assert p2 is not None
    assert (p1.status, p2.status, p2.contents) == ("superseded", "executed", {"x": "p2"})
    assert account.get_proposal(store._connect(), "nope") is None


def test_a_nonce_can_be_spent_once(store: Store) -> None:
    with store.tx() as con:
        assert not account.nonce_used(con, "n1")
        account.use_nonce(con, "n1", "p1", NOW)
        assert account.nonce_used(con, "n1")
    with pytest.raises(sqlite3.IntegrityError), store.tx() as con:
        account.use_nonce(con, "n1", "p1", NOW)


def test_cash_and_positions(store: Store) -> None:
    with store.tx() as con:
        assert account.cash(con, "s1") == 0
        account.set_cash(con, "s1", D("6000.00"))
        account.set_cash(con, "s1", D("4200.00"))
        account.set_units(con, "s1", "USE01", D("12.5"))
        account.set_units(con, "s1", "GOV01", D(0))
    with store.tx() as con:
        assert account.cash(con, "s1") == D("4200.00")
        assert account.positions(con, "s1") == {"USE01": D("12.5")}


def order(oid: str, amount: str, source: str = "user", side: Side = Side.BUY) -> account.OrderRow:
    return account.OrderRow(oid, "p1", "USE01", side, D(amount), D(1), D(10), "2019-10", source)


def test_orders_and_the_daily_total_for_lim_01(store: Store) -> None:
    with store.tx() as con:
        account.add_order(con, "s1", order("o1", "1800.00"), NOW)
        account.add_order(con, "s1", order("o2", "300.00", source="auto_invest"), NOW)
        account.add_order(con, "s1", order("o3", "500.00", side=Side.SELL), NOW)
        account.add_order(con, "s1", order("o4", "100.00"), "2026-10-18T09:00:00+00:00")
    with store.tx() as con:
        assert [o.id for o in account.orders(con, "s1")] == ["o1", "o2", "o3", "o4"]
        assert account.spent_on(con, "s1", "2026-10-17") == D("1800.00")


def test_auto_invest_plan_is_replaced_not_duplicated(store: Store) -> None:
    with store.tx() as con:
        assert account.auto_invest(con, "s1") is None
        account.set_auto_invest(
            con, "s1", account.AutoInvestRow(D(300), {"USE01": 100}, "2019-11", True)
        )
        account.set_auto_invest(
            con, "s1", account.AutoInvestRow(D(250), {"USE01": 100}, "2019-12", True)
        )
    with store.tx() as con:
        plan = account.auto_invest(con, "s1")
    assert plan == account.AutoInvestRow(D(250), {"USE01": 100}, "2019-12", True)


def test_value_history_is_ordered_by_month(store: Store) -> None:
    with store.tx() as con:
        account.record_value(con, "s1", "2019-11", D(6100))
        account.record_value(con, "s1", "2019-10", D(6000))
        account.record_value(con, "s1", "2019-11", D(6150))
    with store.tx() as con:
        assert account.value_history(con, "s1") == [("2019-10", D(6000)), ("2019-11", D(6150))]


def test_cooling_off_lifecycle(store: Store) -> None:
    with store.tx() as con:
        account.add_cooling_off(
            con, "s1", account.CoolingOffRow("c1", "USE01", D(3000), 24.0, "waiting")
        )
    with store.tx() as con:
        assert [c.id for c in account.cooling_offs(con, "s1")] == ["c1"]
        account.set_cooling_off_status(con, "c1", "released")
    with store.tx() as con:
        assert account.cooling_offs(con, "s1") == []
