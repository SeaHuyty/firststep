"""Tools for the shelf: suitable funds, comparisons, glossary."""

from pydantic import Field

from app.core.errors import ToolError
from app.core.reference import Product
from app.core.types import AssetClass
from app.engine.suitability import suitable_funds
from app.store import account
from app.tools.base import Input, Output
from app.tools.cards import ComparisonCard, ComparisonRow, ProductsCard, ProductView, TermCard
from app.tools.context import ToolContext


def product_view(p: Product) -> ProductView:
    """Return a fund as the UI shows it, with the fee on $1,000."""
    return ProductView(
        id=p.id,
        name=p.name,
        asset_class=p.asset_class.value,
        risk_rating=str(p.risk_rating),
        ter_pct=p.ter_pct,
        fee_per_1000_usd=round(p.ter_pct * 10, 2),
        description=p.description,
    )


class ListProductsIn(Input):
    """Optionally narrow the shelf to one asset class."""

    asset_class: AssetClass | None = None


class ListProductsOut(Output):
    """Only funds within the client's class; how many were left out."""

    product_ids: list[str]
    excluded_count: int


def list_suitable_products(ctx: ToolContext, args: ListProductsIn) -> ListProductsOut | ToolError:
    """List the funds the client may hold (SUIT-01)."""
    if ctx.client_class is None:
        return ToolError(code="no_profile", message="Let's finish your risk questions first.")
    shelf = [p for p in ctx.ref.products.values() if args.asset_class in (None, p.asset_class)]
    keep, dropped = suitable_funds(
        shelf, ctx.client_class, ctx.ref.rules.suit_01.max_rating_for_class
    )
    ctx.cards.append(
        ProductsCard(
            products=[product_view(p) for p in keep],
            excluded_count=dropped,
            client_class=str(ctx.client_class),
        )
    )
    return ListProductsOut(product_ids=[p.id for p in keep], excluded_count=dropped)


class CompareIn(Input):
    """Two to four funds to compare."""

    product_ids: list[str] = Field(
        min_length=2, max_length=4, description="2 to 4 fund IDs from FUNDS, e.g. USE01"
    )


class CompareOut(Output):
    """The comparison rows."""

    rows: list[ComparisonRow]


def _history_stats(ctx: ToolContext, pid: str) -> tuple[float | None, float | None]:
    """Return (5-year yearly return %, worst 12-month %) to date."""
    navs = ctx.prices.history(pid, ctx.session.sim_month, months_back=10_000)
    five = (navs[-1] / navs[-61]) ** (1 / 5) - 1 if len(navs) > 60 else None
    worst = min((navs[i] / navs[i - 12] - 1 for i in range(12, len(navs))), default=None)
    return (
        None if five is None else round(five * 100, 1),
        None if worst is None else round(worst * 100, 1),
    )


def compare_products(ctx: ToolContext, args: CompareIn) -> CompareOut | ToolError:
    """Compare fees, risk, history and access to money for 2-4 funds."""
    unknown = [pid for pid in args.product_ids if pid not in ctx.ref.products]
    if unknown:
        return ToolError(code="unknown_product", message=f"I don't have {', '.join(unknown)}.")
    plan = account.latest_proposal(ctx.con, ctx.session.id, "allocation")
    in_plan = set(plan.contents.get("weights", {})) if plan else set()
    rows = []
    for pid in args.product_ids:
        p = ctx.ref.products[pid]
        five, worst = _history_stats(ctx, pid)
        rows.append(
            ComparisonRow(
                id=p.id,
                name=p.name,
                risk_rating=str(p.risk_rating),
                ter_pct=p.ter_pct,
                fee_per_year_on_1000_usd=round(p.ter_pct * 10, 2),
                return_5y_pct_a_year=five,
                worst_12m_pct=worst,
                liquidity_days=p.liquidity_days,
                in_plan=pid in in_plan,
            )
        )
    ctx.cards.append(ComparisonCard(rows=rows, as_of=ctx.session.sim_month))
    return CompareOut(rows=rows)


class ExplainIn(Input):
    """A glossary term (e.g. "etf", "volatility") or a rule ID."""

    topic: str = Field(max_length=40)


class ExplainOut(Output):
    """A fixed definition and its source."""

    term: str
    text: str
    source: str


def explain(ctx: ToolContext, args: ExplainIn) -> ExplainOut | ToolError:
    """Return a fixed, cited definition; Sprout never makes these up.

    For what a word means (index fund, diversification). A question
    about the client's own money goes to the plan's tools instead.
    """
    key = args.topic.strip().lower().replace(" ", "_").replace("-", "_")
    glossary = ctx.ref.glossary
    term = glossary.terms.get(key) or next(
        (t for t in glossary.terms.values() if t.term.lower() == args.topic.strip().lower()), None
    )
    if term is not None:
        source = glossary.sources[term.source]
        ctx.cards.append(
            TermCard(
                term=term.term, text=term.text, source_title=source.title, source_url=source.url
            )
        )
        return ExplainOut(term=term.term, text=term.text, source=source.title)
    rule = ctx.ref.rules.model_dump(by_alias=True).get(args.topic.strip().upper())
    if isinstance(rule, dict) and "description" in rule:
        return ExplainOut(
            term=args.topic.upper(), text=rule["description"], source="data/rules.yaml"
        )
    return ToolError(code="unknown_topic", message="I don't have a definition for that yet.")
