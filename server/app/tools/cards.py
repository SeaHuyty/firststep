"""The cards the UI renders under Sprout's messages.

Every number on a card comes from a tool; the frontend only formats.
The `type` field tells the client which component to use.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class _Card(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Chip(_Card):
    """One quick reply."""

    label: str
    value: object


class QuestionCard(_Card):
    """The next question, with tappable answers."""

    type: Literal["question"] = "question"
    question_id: str
    prompt: str
    why: str
    kind: str
    chips: list[Chip]
    section: str = ""  # the part of the journey, e.g. "Money check"
    step: int
    of: int


class WhyLine(_Card):
    """One reason behind a number, with its rule when there is one."""

    rule_id: str | None
    text: str


class ReadinessCard(_Card):
    """Green "ready" or amber "not yet"."""

    type: Literal["readiness"] = "readiness"
    ready: bool
    emergency_months: float
    investable_monthly_usd: float
    reasons: list[WhyLine]


class PlanStepView(_Card):
    """One step of the savings plan."""

    action: str
    title: str
    monthly_usd: float
    months: int
    target_usd: float
    interest_usd: float


class SavingsPlanCard(_Card):
    """The plan instead of a portfolio."""

    type: Literal["savings_plan"] = "savings_plan"
    steps: list[PlanStepView]
    months_to_ready: int | None
    ready_month: str | None


class RiskBadgeCard(_Card):
    """The C1-C5 reveal."""

    type: Literal["risk_badge"] = "risk_badge"
    client_class: str
    label: str
    summary: str
    tolerance: int
    capacity: int
    horizon_cap: str | None
    limited_by: str
    why: list[WhyLine]
    # A plan at this level in its worst and best 12 months since 2000.
    worst_12m_pct: float
    best_12m_pct: float


class GoalCard(_Card):
    """The goal as set."""

    type: Literal["goal"] = "goal"
    name: str
    target_usd: float
    horizon_years: float
    lump_sum_usd: float
    monthly_usd: float
    client_class: str
    capped: bool


class ProductView(_Card):
    """One fund as listed or compared."""

    id: str
    name: str
    asset_class: str
    risk_rating: str
    ter_pct: float
    fee_per_1000_usd: float
    description: str


class ProductsCard(_Card):
    """The suitable shelf."""

    type: Literal["products"] = "products"
    products: list[ProductView]
    excluded_count: int
    client_class: str


class ComparisonRow(_Card):
    """One fund in a comparison table."""

    id: str
    name: str
    risk_rating: str
    ter_pct: float
    fee_per_year_on_1000_usd: float
    return_5y_pct_a_year: float | None
    worst_12m_pct: float | None
    liquidity_days: int


class ComparisonCard(_Card):
    """Two to four funds side by side."""

    type: Literal["comparison"] = "comparison"
    rows: list[ComparisonRow]
    as_of: str


class AllocationLine(_Card):
    """One fund in a proposed plan."""

    product_id: str
    name: str
    family: str
    risk_rating: str
    weight_pct: float
    amount_usd: str
    why: list[WhyLine]


class AllocationCard(_Card):
    """A proposed plan: donut families plus the fund table."""

    type: Literal["allocation"] = "allocation"
    proposal_id: str
    client_class: str
    label: str
    families: dict[str, float]
    lines: list[AllocationLine]
    total_usd: str
    fee_pct: float
    fee_usd_a_year: float
    # This mix in its worst and best 12 months since 2000, in percent
    # and in the person's own money.
    worst_12m_pct: float
    best_12m_pct: float
    worst_12m_usd: str
    best_12m_usd: str


class ProjectionCard(_Card):
    """Range of outcomes (never called a backtest)."""

    type: Literal["projection"] = "projection"
    proposal_id: str
    years: list[int]
    p10: list[float]
    p50: list[float]
    p90: list[float]
    paid_in: list[float]
    prob_below_paid_in_year1: float
    prob_reach_goal: float | None
    goal_usd: float | None
    caption: str


class OrderView(_Card):
    """One order to confirm, or one fill."""

    product_id: str
    name: str
    side: str
    amount_usd: str
    units: str | None = None
    nav_usd: str | None = None


class ConfirmCard(_Card):
    """Exactly what will happen if the user presses Confirm."""

    type: Literal["confirm"] = "confirm"
    proposal_id: str
    kind: str
    orders: list[OrderView]
    total_usd: str
    monthly_usd: str | None
    fee_usd_a_year: float
    button: str


class ReceiptCard(_Card):
    """A calm receipt after orders fill."""

    type: Literal["receipt"] = "receipt"
    proposal_id: str
    fills: list[OrderView]
    cash_usd: str
    monthly_usd: str | None
    sim_month: str
    audit_head: str


class HoldingView(_Card):
    """One holding in the portfolio."""

    product_id: str
    name: str
    family: str
    units: str
    value_usd: str
    weight_pct: float
    target_pct: float


class PortfolioCard(_Card):
    """The paper account now."""

    type: Literal["portfolio"] = "portfolio"
    sim_month: str
    holdings: list[HoldingView]
    cash_usd: str
    value_usd: str
    paid_in_usd: str
    gain_usd: str
    drawdown_pct: float
    max_drift_pts: float


class AlertCard(_Card):
    """Something that happened while time moved forward."""

    type: Literal["alert"] = "alert"
    tone: Literal["info", "success", "pause", "error"]
    title: str
    text: str
    rule_id: str | None = None
    sim_month: str


class RefusalCard(_Card):
    """A rule said no: what, why, what instead."""

    type: Literal["refusal"] = "refusal"
    rule_id: str
    title: str
    text: str
    next_step: str


class PauseCard(_Card):
    """Amber "not yet" or cooling-off; never an error."""

    type: Literal["pause"] = "pause"
    rule_id: str
    title: str
    text: str
    until_month: str | None = None


class TermCard(_Card):
    """A glossary definition with its source."""

    type: Literal["term"] = "term"
    term: str
    text: str
    source_title: str
    source_url: str


Card = Annotated[
    QuestionCard
    | ReadinessCard
    | SavingsPlanCard
    | RiskBadgeCard
    | GoalCard
    | ProductsCard
    | ComparisonCard
    | AllocationCard
    | ProjectionCard
    | ConfirmCard
    | ReceiptCard
    | PortfolioCard
    | AlertCard
    | RefusalCard
    | PauseCard
    | TermCard,
    Field(discriminator="type"),
]
