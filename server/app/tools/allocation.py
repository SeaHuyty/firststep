"""Tools that propose a plan and show its range of outcomes."""

import secrets
from decimal import Decimal

from pydantic import Field

from app.core.errors import ToolError
from app.core.hashing import content_hash
from app.core.types import FAMILY_OF, ClientClass, to_money
from app.engine.allocation import family_split, split_amount
from app.engine.bootstrap import portfolio_returns, project_outcomes, rolling_extremes
from app.engine.suitability import suitable_funds, weighted_fee_pct, weights_by_class
from app.store import account
from app.tools.base import Input, NoArgs, Output
from app.tools.cards import AllocationCard, AllocationLine, ProjectionCard, WhyLine
from app.tools.context import ToolContext

PROJECTION_CAPTION = (
    "Range of outcomes from replaying past markets (2000 to today) in many orders. "
    "Not a prediction. Before inflation and taxes."
)


def content_of(
    weights: dict[str, float], ctx: ToolContext, client: ClientClass
) -> dict[str, object]:
    """Return a proposal's contents: mix, money and class."""
    goal = ctx.session.profile.goal
    return {
        "weights": weights,
        "total_usd": str(to_money(goal.lump_sum_usd if goal else 0)),
        "monthly_usd": str(to_money(goal.monthly_usd if goal else 0)),
        "client_class": str(client),
    }


def history_extremes(ctx: ToolContext, weights: dict[str, float]) -> tuple[float, float]:
    """Return a mix's worst and best 12 months in history to date."""
    end = ctx.prices.index(ctx.session.sim_month) + 1
    series = {a: s[:end] for a, s in ctx.ref.returns.series.items()}
    monthly = portfolio_returns(
        weights_by_class(weights, ctx.ref.products),
        series,
        weighted_fee_pct(weights, ctx.ref.products),
    )
    return rolling_extremes(monthly)


class ProposeOut(Output):
    """The proposal id and its main numbers."""

    proposal_id: str
    client_class: str
    weights: dict[str, float]
    fee_pct: float
    fee_usd_a_year: float


def _why(ctx: ToolContext, pid: str, weight: float, client: ClientClass) -> list[WhyLine]:
    p, rules = ctx.ref.products[pid], ctx.ref.rules
    return [
        WhyLine(rule_id="SUIT-01", text=f"Rated {p.risk_rating}, within your {client} limit."),
        WhyLine(
            rule_id="CONC-01",
            text=f"{weight:g}% of your plan, under the {rules.conc_01.max_product_pct:g}% limit "
            "for any one fund.",
        ),
        WhyLine(rule_id=None, text=f"Low cost: {p.ter_pct:.2f}% a year."),
    ]


def _peers(ctx: ToolContext, pid: str, client: ClientClass, plan: dict[str, float]) -> list[str]:
    """Return up to 3 similar funds within the client's level."""
    kind = ctx.ref.products[pid].asset_class
    alike = [p for p in ctx.ref.products.values() if p.asset_class == kind and p.id not in plan]
    keep, _ = suitable_funds(alike, client, ctx.ref.rules.suit_01.max_rating_for_class)
    return [p.id for p in sorted(keep, key=lambda p: (p.ter_pct, p.id))[:3]]


def _propose(ctx: ToolContext, weights: dict[str, float], label: str) -> ProposeOut | ToolError:
    client, goal = ctx.client_class, ctx.session.profile.goal
    if client is None or goal is None:
        return ToolError(code="no_goal", message="Let's set your goal first.")
    total = to_money(goal.lump_sum_usd)
    lines = split_amount(weights, total) if total > 0 else ()
    amounts = {line.product_id: line.amount_usd for line in lines}
    fee_pct = weighted_fee_pct(weights, ctx.ref.products)
    proposal_id = f"al_{secrets.token_hex(6)}"
    contents = content_of(weights, ctx, client)
    account.save_proposal(
        ctx.con,
        proposal_id=proposal_id,
        session_id=ctx.session.id,
        kind="allocation",
        contents=contents,
        content_hash=content_hash(contents),
        now=ctx.iso_now(),
    )
    fee_usd = float(total) * fee_pct / 100
    worst, best = history_extremes(ctx, weights)
    ctx.cards.append(
        AllocationCard(
            proposal_id=proposal_id,
            client_class=str(client),
            label=label,
            families={
                f.value: round(w, 1) for f, w in family_split(weights, ctx.ref.products).items()
            },
            lines=[
                AllocationLine(
                    product_id=pid,
                    name=ctx.ref.products[pid].name,
                    family=FAMILY_OF[ctx.ref.products[pid].asset_class].value,
                    risk_rating=str(ctx.ref.products[pid].risk_rating),
                    weight_pct=w,
                    amount_usd=str(amounts.get(pid, Decimal(0))),
                    why=_why(ctx, pid, w, client),
                    peers=_peers(ctx, pid, client, weights),
                )
                for pid, w in weights.items()
            ],
            total_usd=str(total),
            fee_pct=round(fee_pct, 3),
            fee_usd_a_year=round(fee_usd, 2),
            worst_12m_pct=round(worst * 100, 1),
            best_12m_pct=round(best * 100, 1),
            worst_12m_usd=str(to_money(total * Decimal(str(1 + worst)))),
            best_12m_usd=str(to_money(total * Decimal(str(1 + best)))),
        )
    )
    return ProposeOut(
        proposal_id=proposal_id,
        client_class=str(client),
        weights=weights,
        fee_pct=round(fee_pct, 3),
        fee_usd_a_year=round(fee_usd, 2),
    )


def propose_allocation(ctx: ToolContext, _: NoArgs) -> ProposeOut | ToolError:
    """Propose the model portfolio for the client's class."""
    if ctx.client_class is None:
        return ToolError(code="no_profile", message="Let's finish your risk questions first.")
    model = ctx.ref.portfolios[ctx.client_class]
    return _propose(ctx, dict(model.weights), f"{ctx.client_class} {model.label}")


class CustomLine(Input):
    """One fund and its share of a requested mix."""

    product_id: str = Field(max_length=10, description="A fund ID from FUNDS")
    weight_pct: float = Field(gt=0, le=100, description="Share of the whole plan, in percent")


class ProposeCustomIn(Input):
    """A specific mix the client asked for, e.g. "all in tech"."""

    lines: list[CustomLine] = Field(
        min_length=1,
        max_length=10,
        description="The whole new mix, every fund to hold; weights add up to 100",
    )


def propose_custom_allocation(ctx: ToolContext, args: ProposeCustomIn) -> ProposeOut | ToolError:
    """Propose the client's own mix; the guardian checks it first."""
    unknown = [x.product_id for x in args.lines if x.product_id not in ctx.ref.products]
    if unknown:
        return ToolError(code="unknown_product", message=f"I don't have {', '.join(unknown)}.")
    weights = {x.product_id: x.weight_pct for x in args.lines}
    if abs(sum(weights.values()) - 100) > 0.01:
        return ToolError(code="bad_weights", message="The shares need to add up to 100%.")
    return _propose(ctx, weights, "Your mix")


class ProjectOut(Output):
    """Year-end bad, typical and good cases."""

    years: list[int]
    p10: list[float]
    p50: list[float]
    p90: list[float]
    prob_below_paid_in_year1: float
    prob_reach_goal: float | None


def project_outcomes_tool(ctx: ToolContext, _: NoArgs) -> ProjectOut | ToolError:
    """Show the range of outcomes of the latest proposal.

    Bad, typical and good cases from replaying past markets. Use it
    when the client asks what could happen to their money: how bad it
    could get, or what they might end up with.
    """
    proposal = account.latest_proposal(ctx.con, ctx.session.id, "allocation")
    goal = ctx.session.profile.goal
    if proposal is None or goal is None:
        return ToolError(code="no_proposal", message="Let's make a plan first.")
    weights = {k: float(v) for k, v in proposal.contents["weights"].items()}
    # History only up to the session's month, so a simulated past never
    # peeks at its own future.
    end = ctx.prices.index(ctx.session.sim_month) + 1
    series = {a: s[:end] for a, s in ctx.ref.returns.series.items()}
    monthly = portfolio_returns(
        weights_by_class(weights, ctx.ref.products),
        series,
        weighted_fee_pct(weights, ctx.ref.products),
    )
    years = max(1, round(goal.horizon_years))
    r = project_outcomes(
        monthly,
        lump_sum_usd=goal.lump_sum_usd,
        monthly_usd=goal.monthly_usd,
        years=years,
        goal_usd=goal.target_usd,
    )
    ctx.cards.append(
        ProjectionCard(
            proposal_id=proposal.id,
            years=list(r.years),
            p10=list(r.p10),
            p50=list(r.p50),
            p90=list(r.p90),
            paid_in=list(r.paid_in),
            prob_below_paid_in_year1=round(r.prob_loss_year1, 3),
            prob_reach_goal=None if r.prob_reach_goal is None else round(r.prob_reach_goal, 3),
            goal_usd=goal.target_usd,
            caption=PROJECTION_CAPTION,
        )
    )
    return ProjectOut(
        years=list(r.years),
        p10=list(r.p10),
        p50=list(r.p50),
        p90=list(r.p90),
        prob_below_paid_in_year1=round(r.prob_loss_year1, 3),
        prob_reach_goal=r.prob_reach_goal,
    )
