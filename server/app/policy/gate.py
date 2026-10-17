"""The guardian's checks before a tool runs, whoever asked for it.

STAGE-01 applies to every tool. Tools that move or commit money get
their own checks on top. The executor calls `check` for every call from
a chip, a button or the LLM, so no path skips the rules.
"""

from datetime import datetime
from decimal import Decimal

from app.core.types import Side, to_money
from app.engine.allocation import split_amount
from app.policy.engine import ALLOW, Decision, Policy
from app.store import account
from app.tools.allocation import ProposeCustomIn
from app.tools.base import Input
from app.tools.broker import PlaceOrderIn
from app.tools.context import ToolContext


def _buys(orders: list[dict[str, str]]) -> list[Decimal]:
    return [Decimal(o["amount_usd"]) for o in orders if o["side"] == Side.BUY.value]


def _check_custom(policy: Policy, ctx: ToolContext, args: ProposeCustomIn) -> Decision:
    if ctx.client_class is None:
        return ALLOW  # the tool itself explains that a profile is needed
    weights = {x.product_id: x.weight_pct for x in args.lines if x.product_id in policy.products}
    return policy.allocation(weights, ctx.client_class)


def _check_prepare(policy: Policy, ctx: ToolContext) -> Decision:
    plan = account.latest_proposal(ctx.con, ctx.session.id, "allocation")
    if plan is None or ctx.client_class is None:
        return ALLOW
    weights = {k: float(v) for k, v in plan.contents["weights"].items()}
    first = policy.allocation(weights, ctx.client_class)
    if not first.allowed:
        return first
    total = to_money(plan.contents["total_usd"])
    amounts = [line.amount_usd for line in split_amount(weights, total)] if total > 0 else []
    spent = account.spent_on(ctx.con, ctx.session.id, ctx.now.date().isoformat())
    return policy.order_limits(amounts, spent)


def _check_place(policy: Policy, ctx: ToolContext, args: PlaceOrderIn, now: datetime) -> Decision:
    proposal = account.get_proposal(ctx.con, args.proposal_id)
    if proposal is None:
        return Decision(False, "CONF-01", "That plan can't be placed now.")
    confirmed = policy.confirmation(
        args.confirmation_token,
        proposal_id=proposal.id,
        contents_sha256=proposal.content_hash,
        now=now,
        nonce_used=lambda n: account.nonce_used(ctx.con, n),
    )
    if not confirmed.allowed:
        return confirmed
    orders = proposal.contents["orders"]
    buys = {o["product_id"]: 1.0 for o in orders if o["side"] == Side.BUY.value}
    if buys and ctx.client_class is not None:
        suitable = policy.suitability(buys, ctx.client_class)
        if not suitable.allowed:
            return suitable
    return policy.order_limits(
        _buys(orders), account.spent_on(ctx.con, ctx.session.id, now.date().isoformat())
    )


def check(policy: Policy, tool: str, args: Input, ctx: ToolContext) -> Decision:
    """Return the guardian's decision on one tool call."""
    decision = policy.stage(tool, ctx.session.stage)
    if decision.allowed:
        if isinstance(args, ProposeCustomIn):
            decision = _check_custom(policy, ctx, args)
        elif tool == "prepare_orders":
            decision = _check_prepare(policy, ctx)
        elif isinstance(args, PlaceOrderIn):
            decision = _check_place(policy, ctx, args, ctx.now)
    return decision
