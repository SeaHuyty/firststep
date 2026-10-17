"""What every tool receives.

Reference data, the open transaction and the session it acts on. Tools
change `session` and append `cards`; the executor saves both when the
tool returns.
"""

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from functools import cached_property

from app.core.profile import Profile
from app.core.reference import Reference
from app.core.types import ClientClass, Stage
from app.engine.monitor import next_nav
from app.tools.cards import Card

NAV_START = 10.0
HOURS_PER_MONTH = 730.0
UNITS = Decimal("0.000001")
CENT = Decimal("0.01")


@dataclass
class SessionState:
    """The mutable part of a session during one tool call."""

    id: str
    persona: str | None
    stage: Stage
    profile: Profile
    sim_month: str
    sim_offset_hours: float


class Prices:
    """Simulated fund prices.

    Each fund starts at $10.00 in December 1999 and moves by its asset
    class's monthly return minus a twelfth of its yearly fee.
    """

    def __init__(self, ref: Reference) -> None:
        """Build every fund's monthly price series once."""
        self.months = ref.returns.months
        self._index = {m: i for i, m in enumerate(self.months)}
        self._navs: dict[str, list[float]] = {}
        for pid, product in ref.products.items():
            nav, series = NAV_START, []
            for r in ref.returns.series[product.asset_class]:
                nav = next_nav(nav, r, product.ter_pct)
                series.append(nav)
            self._navs[pid] = series

    def index(self, month: str) -> int:
        """Return the position of a month in the data."""
        return self._index[month]

    def nav(self, product_id: str, month: str) -> Decimal:
        """Return a fund's month-end price, to the cent."""
        value = Decimal(str(self._navs[product_id][self._index[month]]))
        return value.quantize(CENT, rounding=ROUND_HALF_UP)

    def history(self, product_id: str, month: str, months_back: int) -> list[float]:
        """Return up to months_back prices ending at month."""
        end = self._index[month] + 1
        return self._navs[product_id][max(0, end - months_back) : end]

    def next_month(self, month: str) -> str | None:
        """Return the month after, or None at the end of the data."""
        i = self._index[month] + 1
        return self.months[i] if i < len(self.months) else None


@dataclass
class ToolContext:
    """Everything one tool call can see and change."""

    ref: Reference
    prices: Prices
    con: sqlite3.Connection
    session: SessionState
    now: datetime
    cards: list[Card] = field(default_factory=list)

    @cached_property
    def client_class(self) -> ClientClass | None:
        """Return the scored class, or None before profiling."""
        risk = self.session.profile.risk
        return risk.final_class if risk else None

    def iso_now(self) -> str:
        """Return the wall-clock time as ISO text."""
        return self.now.isoformat(timespec="seconds")
