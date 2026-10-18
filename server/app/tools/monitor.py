"""Tools that watch the paper account and move simulated time."""

import secrets
from decimal import Decimal

from pydantic import Field, model_validator

from app.core.errors import ToolError
from app.core.types import CENT, FAMILY_OF, Side, Stage
from app.engine.allocation import split_amount
from app.engine.monitor import drift
from app.store import account
from app.tools.base import Input, NoArgs, Output
from app.tools.cards import AlertCard, HoldingView, PortfolioCard
from app.tools.context import HOURS_PER_MONTH, UNITS, ToolContext
from app.tools.portfolio import fund_drawdown, growth_drawdown, target_weights, value


class PortfolioOut(Output):
    """The account in numbers."""

    sim_month: str
    value_usd: str
    cash_usd: str
    paid_in_usd: str
    drawdown_pct: float
    max_drift_pts: float
    holdings: dict[str, str]


def _paid_in(ctx: ToolContext) -> Decimal:
    goal = ctx.session.profile.goal
    lump = Decimal(str(goal.lump_sum_usd)) if goal else Decimal(0)
    return (lump + account.auto_invested(ctx.con, ctx.session.id)).quantize(CENT)


def get_portfolio(ctx: ToolContext, _: NoArgs) -> PortfolioOut:
    """Show holdings, value, gain and drift at the simulated month."""
    v, target = value(ctx), target_weights(ctx)
    d = (
        drift(v.values, target, ctx.ref.products, ctx.ref.rules.drift_01.max_drift_pts)
        if target
        else None
    )
    paid_in = _paid_in(ctx)
    invested = v.invested if v.invested > 0 else Decimal(1)
    holdings = [
        HoldingView(
            product_id=pid,
            name=ctx.ref.products[pid].name,
            family=FAMILY_OF[ctx.ref.products[pid].asset_class].value,
            units=str(account.positions(ctx.con, ctx.session.id).get(pid, Decimal(0))),
            value_usd=str(amount),
            weight_pct=round(float(amount / invested * 100), 1),
            target_pct=target.get(pid, 0.0),
        )
        for pid, amount in v.values.items()
    ]
    drawdown = round(growth_drawdown(ctx), 1)
    max_drift = round(d.max_drift_pts, 1) if d else 0.0
    ctx.cards.append(
        PortfolioCard(
            sim_month=ctx.session.sim_month,
            holdings=holdings,
            cash_usd=str(v.cash),
            value_usd=str(v.total),
            paid_in_usd=str(paid_in),
            gain_usd=str(v.total - paid_in),
            drawdown_pct=drawdown,
            max_drift_pts=max_drift,
        )
    )
    return PortfolioOut(
        sim_month=ctx.session.sim_month,
        value_usd=str(v.total),
        cash_usd=str(v.cash),
        paid_in_usd=str(paid_in),
        drawdown_pct=drawdown,
        max_drift_pts=max_drift,
        holdings={pid: str(amount) for pid, amount in v.values.items()},
    )


class AdvanceIn(Input):
    """How far to fast-forward: a number of months or a target month."""

    months: int | None = Field(
        default=None, ge=1, le=24, description="Months to move forward, e.g. 12 for a year"
    )
    until: str | None = Field(
        default=None, pattern=r"^\d{4}-\d{2}$", description="A month to jump to, YYYY-MM"
    )

    @model_validator(mode="after")
    def _one_of(self) -> "AdvanceIn":
        if (self.months is None) == (self.until is None):
            raise ValueError("give either months or until")
        return self


class AdvanceOut(Output):
    """The new month, what happened, and where the plan stands."""

    new_month: str
    events: list[str]
    value_usd: str
    paid_in_usd: str


def _auto_invest(ctx: ToolContext, month: str) -> str | None:
    plan = account.auto_invest(ctx.con, ctx.session.id)
    if plan is None or not plan.active or plan.next_month > month:
        return None
    cash = account.cash(ctx.con, ctx.session.id) + plan.monthly  # the simulated monthly deposit
    units = account.positions(ctx.con, ctx.session.id)
    for line in split_amount(plan.weights, plan.monthly):
        nav = ctx.prices.nav(line.product_id, month)
        qty = (line.amount_usd / nav).quantize(UNITS)
        units[line.product_id] = units.get(line.product_id, Decimal(0)) + qty
        account.set_units(ctx.con, ctx.session.id, line.product_id, units[line.product_id])
        account.add_order(
            ctx.con,
            ctx.session.id,
            account.OrderRow(
                f"o_{secrets.token_hex(5)}",
                None,
                line.product_id,
                Side.BUY,
                line.amount_usd,
                qty,
                nav,
                month,
                "auto_invest",
            ),
            ctx.iso_now(),
        )
        cash -= line.amount_usd
    account.set_cash(ctx.con, ctx.session.id, cash)
    nxt = ctx.prices.next_month(month)
    account.set_auto_invest(
        ctx.con,
        ctx.session.id,
        plan.__class__(plan.monthly, plan.weights, nxt or month, nxt is not None),
    )
    return f"auto_invest:{plan.monthly}"


def _alerts(ctx: ToolContext, month: str, alerted: set[str]) -> list[str]:
    """Return new events this month and add their cards (once each)."""
    events = []
    rule = ctx.ref.rules.cool_01
    fallen = {
        pid: dd
        for pid in account.positions(ctx.con, ctx.session.id)
        if (dd := fund_drawdown(ctx, pid)) > rule.drawdown_pct
    }
    if fallen and "drop" not in alerted:
        alerted.add("drop")
        worst = max(fallen, key=fallen.__getitem__)
        others = len(fallen) - 1
        also = f" ({others} other fund{'s' if others != 1 else ''} also fell)" if others else ""
        events += [f"drawdown:{pid}:{dd:.0f}" for pid, dd in fallen.items()]
        ctx.cards.append(
            AlertCard(
                tone="pause",
                title="Markets have dropped",
                text=f"{ctx.ref.products[worst].name} is {fallen[worst]:.0f}% below its high"
                f"{also}. Drops like this have happened before, and selling after a fall locks "
                "in the loss. Your plan was built for years, not months.",
                rule_id="COOL-01",
                sim_month=month,
            )
        )
    target = target_weights(ctx)
    if target and "drift" not in alerted:
        d = drift(
            value(ctx).values, target, ctx.ref.products, ctx.ref.rules.drift_01.max_drift_pts
        )
        if d.needs_rebalance:
            alerted.add("drift")
            events.append(f"drift:{d.max_drift_pts:.1f}")
            ctx.cards.append(
                AlertCard(
                    tone="info",
                    title="Your mix has drifted",
                    text=f"One part of your plan is {d.max_drift_pts:.1f} points away from its "
                    "target. I can show you a rebalance to bring it back.",
                    rule_id="DRIFT-01",
                    sim_month=month,
                )
            )
    return events


def _release_cooling_offs(ctx: ToolContext, month: str) -> list[str]:
    events = []
    for c in account.cooling_offs(ctx.con, ctx.session.id):
        if ctx.session.sim_offset_hours >= c.until_hours:
            account.set_cooling_off_status(ctx.con, c.id, "released")
            events.append(f"cooling_off_ended:{c.product_id}")
            ctx.cards.append(
                AlertCard(
                    tone="info",
                    title="Your 24 hours are up",
                    text=f"You asked to sell {ctx.ref.products[c.product_id].name}. Do you still "
                    "want to? Nothing has been sold.",
                    rule_id="COOL-01",
                    sim_month=month,
                )
            )
    return events


def advance_time(ctx: ToolContext, args: AdvanceIn) -> AdvanceOut | ToolError:
    """Fast-forward through history month by month (demo only)."""
    if not account.positions(ctx.con, ctx.session.id):
        return ToolError(
            code="no_portfolio", message="Place your first orders, then we can fast-forward."
        )
    steps = args.months or 0
    if args.until is not None:
        if args.until <= ctx.session.sim_month or args.until not in ctx.prices.months:
            return ToolError(code="bad_month", message="Pick a later month inside 2000-2025.")
        steps = ctx.prices.index(args.until) - ctx.prices.index(ctx.session.sim_month)
    events: list[str] = []
    alerted: set[str] = set()
    history = account.value_history(ctx.con, ctx.session.id)
    growth = history[-1][1] if history else Decimal(100)
    for _ in range(steps):
        month = ctx.prices.next_month(ctx.session.sim_month)
        if month is None:
            events.append("end_of_data")
            break
        before = value(ctx).invested
        after = value(ctx, month).invested
        if before > 0:
            growth = (growth * after / before).quantize(Decimal("0.0001"))
        ctx.session.sim_month = month
        ctx.session.sim_offset_hours += HOURS_PER_MONTH
        account.record_value(ctx.con, ctx.session.id, month, growth)
        if (e := _auto_invest(ctx, month)) is not None:
            events.append(e)
        events += _release_cooling_offs(ctx, month)
        events += _alerts(ctx, month, alerted)
    if ctx.session.stage == Stage.EXECUTED:
        ctx.session.stage = Stage.MONITOR
    now = get_portfolio(ctx, NoArgs())
    return AdvanceOut(
        new_month=ctx.session.sim_month,
        events=events,
        value_usd=now.value_usd,
        paid_in_usd=now.paid_in_usd,
    )


def check_drift(ctx: ToolContext, _: NoArgs) -> PortfolioOut | ToolError:
    """Show how far the mix is from target (DRIFT-01)."""
    if not target_weights(ctx):
        return ToolError(code="no_portfolio", message="There's no confirmed plan yet.")
    return get_portfolio(ctx, NoArgs())
