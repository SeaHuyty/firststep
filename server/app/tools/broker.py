"""Tools that prepare and place simulated orders.

`prepare_orders`, `propose_rebalance` and `request_sell` only draft a
proposal and show a confirm card (Tier 1). `place_order` (Tier 2) runs
only from the user's Confirm click, after the guardian has checked the
one-time token (CONF-01), the limits (LIM-01) and suitability.
"""

import secrets
from decimal import Decimal

from pydantic import Field

from app.core.errors import ToolError
from app.core.hashing import content_hash
from app.core.types import CENT, Side, Stage, to_money
from app.engine.allocation import split_amount
from app.engine.monitor import needs_cooling_off, rebalance_trades
from app.engine.suitability import weighted_fee_pct
from app.store import account
from app.tools.base import Input, NoArgs, Output
from app.tools.cards import ConfirmCard, OrderView, PauseCard, ReceiptCard
from app.tools.context import HOURS_PER_MONTH, UNITS, ToolContext
from app.tools.portfolio import GROWTH_START, fund_drawdown, target_weights, value


class DraftOut(Output):
    """A proposal waiting for the user's Confirm click."""

    proposal_id: str
    orders: list[dict[str, str]]
    total_usd: str


def _order_views(ctx: ToolContext, orders: list[dict[str, str]]) -> list[OrderView]:
    return [
        OrderView(
            product_id=o["product_id"],
            name=ctx.ref.products[o["product_id"]].name,
            side=o["side"],
            amount_usd=o["amount_usd"],
        )
        for o in orders
    ]


def _draft(
    ctx: ToolContext,
    *,
    kind: str,
    orders: list[dict[str, str]],
    weights: dict[str, float],
    monthly: Decimal | None,
    button: str,
) -> DraftOut:
    contents: dict[str, object] = {
        "kind": kind,
        "orders": orders,
        "weights": weights,
        "monthly_usd": None if monthly is None else str(monthly),
        "sim_month": ctx.session.sim_month,
    }
    proposal_id = f"or_{secrets.token_hex(6)}"
    account.save_proposal(
        ctx.con,
        proposal_id=proposal_id,
        session_id=ctx.session.id,
        kind="orders",
        contents=contents,
        content_hash=content_hash(contents),
        now=ctx.iso_now(),
    )
    total = sum((Decimal(o["amount_usd"]) for o in orders), Decimal(0))
    fee = float(total) * weighted_fee_pct(weights, ctx.ref.products) / 100 if weights else 0.0
    ctx.cards.append(
        ConfirmCard(
            proposal_id=proposal_id,
            kind=kind,
            orders=_order_views(ctx, orders),
            total_usd=str(total),
            monthly_usd=None if monthly is None else str(monthly),
            fee_usd_a_year=round(fee, 2),
            button=button,
        )
    )
    if ctx.session.stage == Stage.PROPOSE:
        ctx.session.stage = Stage.CONFIRM
    return DraftOut(proposal_id=proposal_id, orders=orders, total_usd=str(total))


def _plural(n: int) -> str:
    return f"{n} order" if n == 1 else f"{n} orders"


def prepare_orders(ctx: ToolContext, _: NoArgs) -> DraftOut | ToolError:
    """Turn the latest plan into orders the user can confirm."""
    plan = account.latest_proposal(ctx.con, ctx.session.id, "allocation")
    if plan is None:
        return ToolError(code="no_proposal", message="Let's make a plan first.")
    weights = {k: float(v) for k, v in plan.contents["weights"].items()}
    total = Decimal(str(plan.contents["total_usd"]))
    cash = account.cash(ctx.con, ctx.session.id)
    if total > cash:
        return ToolError(
            code="not_enough_cash",
            message=f"The plan needs ${total:,.2f} but the practice account holds ${cash:,.2f}.",
        )
    orders = [
        {"product_id": line.product_id, "side": Side.BUY.value, "amount_usd": str(line.amount_usd)}
        for line in split_amount(weights, total)
    ]
    monthly = Decimal(str(plan.contents.get("monthly_usd") or 0))
    return _draft(
        ctx,
        kind="buy",
        orders=orders,
        weights=weights,
        monthly=monthly if monthly > 0 else None,
        button=f"Confirm and place {_plural(len(orders))}",
    )


class PlaceOrderIn(Input):
    """The confirmed proposal and the token the user's click minted."""

    proposal_id: str = Field(max_length=40)
    confirmation_token: str = Field(max_length=600)


class PlaceOrderOut(Output):
    """What filled."""

    fills: list[dict[str, str]]
    cash_usd: str


def place_order(ctx: ToolContext, args: PlaceOrderIn) -> PlaceOrderOut | ToolError:
    """Fill the confirmed orders at this month's simulated prices."""
    proposal = account.get_proposal(ctx.con, args.proposal_id)
    if proposal is None or proposal.session_id != ctx.session.id or proposal.status != "draft":
        return ToolError(
            code="no_proposal", rule_id="CONF-01", message="That plan can't be placed now."
        )
    month = ctx.session.sim_month
    cash = account.cash(ctx.con, ctx.session.id)
    units = account.positions(ctx.con, ctx.session.id)
    fills = []
    for o in proposal.contents["orders"]:
        pid, side, amount = o["product_id"], Side(o["side"]), Decimal(o["amount_usd"])
        nav = ctx.prices.nav(pid, month)
        qty = (amount / nav).quantize(UNITS)
        if side == Side.SELL:
            qty = min(qty, units.get(pid, Decimal(0)))
            amount = (qty * nav).quantize(CENT)
        units[pid] = units.get(pid, Decimal(0)) + (qty if side == Side.BUY else -qty)
        cash += -amount if side == Side.BUY else amount
        account.set_units(ctx.con, ctx.session.id, pid, units[pid])
        order_id = f"o_{secrets.token_hex(5)}"
        source = "rebalance" if proposal.contents.get("kind") == "rebalance" else "user"
        account.add_order(
            ctx.con,
            ctx.session.id,
            account.OrderRow(order_id, proposal.id, pid, side, amount, qty, nav, month, source),
            ctx.iso_now(),
        )
        fills.append(
            {
                "order_id": order_id,
                "product_id": pid,
                "side": side.value,
                "amount_usd": str(amount),
                "units": str(qty),
                "nav_usd": str(nav),
            }
        )
    if cash < 0:
        raise ValueError("cash went negative; prepare_orders should have stopped this")
    account.set_cash(ctx.con, ctx.session.id, cash)
    account.mark_executed(ctx.con, proposal.id)
    monthly = proposal.contents.get("monthly_usd")
    if monthly and ctx.prices.next_month(month):
        account.set_auto_invest(
            ctx.con,
            ctx.session.id,
            account.AutoInvestRow(
                to_money(monthly),
                proposal.contents["weights"],
                ctx.prices.next_month(month) or month,
                True,
            ),
        )
    if not account.value_history(ctx.con, ctx.session.id):
        account.record_value(ctx.con, ctx.session.id, month, GROWTH_START)
    ctx.cards.append(
        ReceiptCard(
            proposal_id=proposal.id,
            fills=[
                OrderView(
                    product_id=f["product_id"],
                    name=ctx.ref.products[f["product_id"]].name,
                    side=f["side"],
                    amount_usd=f["amount_usd"],
                    units=f["units"],
                    nav_usd=f["nav_usd"],
                )
                for f in fills
            ],
            cash_usd=str(cash),
            monthly_usd=None if not monthly else str(monthly),
            sim_month=month,
            audit_head="",  # filled in by the executor after the fill is logged
        )
    )
    if ctx.session.stage == Stage.CONFIRM:
        ctx.session.stage = Stage.EXECUTED
    return PlaceOrderOut(fills=fills, cash_usd=str(cash))


def propose_rebalance(ctx: ToolContext, _: NoArgs) -> DraftOut | ToolError:
    """Draft the trades that bring the mix back to target (DRIFT-01)."""
    target = target_weights(ctx)
    if not target:
        return ToolError(code="nothing_to_rebalance", message="There's no confirmed plan yet.")
    trades = rebalance_trades(value(ctx).values, target)
    if not trades:
        return ToolError(code="on_target", message="Your mix is already on target.")
    orders = [
        {"product_id": t.product_id, "side": t.side.value, "amount_usd": str(t.amount_usd)}
        for t in trades
    ]
    return _draft(
        ctx,
        kind="rebalance",
        orders=orders,
        weights=target,
        monthly=None,
        button=f"Confirm and place {_plural(len(orders))}",
    )


class RequestSellIn(Input):
    """What to sell: one fund (or everything) and an amount (or all)."""

    product_id: str | None = Field(
        default=None, max_length=10, description="A fund id, or omit to sell everything"
    )
    amount_usd: float | None = Field(
        default=None, gt=0, le=10_000_000, description="Dollars to sell, or omit for all of it"
    )


def _sale_lines(ctx: ToolContext, args: RequestSellIn) -> dict[str, Decimal] | ToolError:
    held = value(ctx).values
    if args.product_id is None:
        return {pid: v for pid, v in held.items() if v > 0}
    have = held.get(args.product_id, Decimal(0))
    if have <= 0:
        return ToolError(code="not_held", message="You don't hold that fund.")
    amount = have if args.amount_usd is None else min(to_money(args.amount_usd), have)
    return {args.product_id: amount}


def request_sell(ctx: ToolContext, args: RequestSellIn) -> DraftOut | ToolError:
    """Draft a sale, or start a cooling-off period first (COOL-01).

    The sale waits when the part of it in funds more than the drawdown
    limit below their 12-month high is over the share limit of the
    portfolio: that is selling right after a fall.
    """
    lines = _sale_lines(ctx, args)
    if isinstance(lines, ToolError):
        return lines
    if not lines:
        return ToolError(code="not_held", message="There's nothing to sell yet.")
    rule = ctx.ref.rules.cool_01
    released = {
        c.product_id
        for c in account.cooling_offs(ctx.con, ctx.session.id, include_released=True)
        if c.status == "released"
    }
    fallen = {
        pid: fund_drawdown(ctx, pid)
        for pid in lines
        if pid not in released and fund_drawdown(ctx, pid) > rule.drawdown_pct
    }
    in_fallen = sum((lines[pid] for pid in fallen), Decimal(0))
    if fallen and needs_cooling_off(
        sell_usd=in_fallen,
        portfolio_usd=value(ctx).total,
        drawdown=max(fallen.values()),
        drawdown_pct_limit=rule.drawdown_pct,
        sell_share_pct_limit=rule.sell_share_pct,
    ):
        until = ctx.session.sim_offset_hours + rule.cooling_off_hours
        for pid in fallen:
            account.add_cooling_off(
                ctx.con,
                ctx.session.id,
                account.CoolingOffRow(
                    f"c_{secrets.token_hex(5)}", pid, lines[pid], until, "waiting"
                ),
            )
        worst = max(fallen, key=fallen.__getitem__)
        name = ctx.ref.products[worst].name
        text = (
            f"{name} is {fallen[worst]:.0f}% below its high. Selling now locks in the drop. "
            f"Big sales after a fall wait {rule.cooling_off_hours:g} hours, then I'll ask again."
        )
        ctx.cards.append(PauseCard(rule_id="COOL-01", title="Let's pause for 24 hours", text=text))
        return ToolError(code="cooling_off", rule_id="COOL-01", message=text)
    orders = [
        {"product_id": pid, "side": Side.SELL.value, "amount_usd": str(amount)}
        for pid, amount in lines.items()
    ]
    return _draft(
        ctx,
        kind="sell",
        orders=orders,
        weights=target_weights(ctx),
        monthly=None,
        button="Confirm and sell" if len(orders) == 1 else f"Confirm and sell {len(orders)} funds",
    )


def months_to_hours(months: int) -> float:
    """Return simulated hours in a number of months."""
    return months * HOURS_PER_MONTH
