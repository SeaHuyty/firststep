"""Valuing the paper account at the session's simulated month."""

from dataclasses import dataclass
from decimal import Decimal

from app.core.types import CENT, Money
from app.engine.monitor import drawdown_pct
from app.store import account
from app.tools.context import ToolContext

GROWTH_START = Decimal(100)


@dataclass(frozen=True, slots=True)
class Valuation:
    """Holdings at today's prices."""

    values: dict[str, Money]
    cash: Money
    invested: Money

    @property
    def total(self) -> Money:
        """Return holdings plus cash."""
        return self.invested + self.cash


def value(ctx: ToolContext, month: str | None = None) -> Valuation:
    """Return each holding's value at a month (default: now)."""
    month = month or ctx.session.sim_month
    units = account.positions(ctx.con, ctx.session.id)
    values = {pid: (u * ctx.prices.nav(pid, month)).quantize(CENT) for pid, u in units.items()}
    return Valuation(
        values=values,
        cash=account.cash(ctx.con, ctx.session.id),
        invested=sum(values.values(), Decimal(0)),
    )


def fund_drawdown(ctx: ToolContext, product_id: str) -> float:
    """Return how far a fund is below its 12-month high, in percent."""
    return drawdown_pct(ctx.prices.history(product_id, ctx.session.sim_month, months_back=13))


def growth_drawdown(ctx: ToolContext) -> float:
    """Return how far the portfolio's growth index is below its peak."""
    history = [float(v) for _, v in account.value_history(ctx.con, ctx.session.id)]
    return drawdown_pct(history)


def target_weights(ctx: ToolContext) -> dict[str, float]:
    """Return the mix the client confirmed (empty before any order)."""
    proposal = account.latest_proposal(ctx.con, ctx.session.id, "orders")
    if proposal is None or proposal.status != "executed":
        return {}
    return {k: float(v) for k, v in proposal.contents.get("weights", {}).items()}
