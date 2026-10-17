"""Tools that learn about the client.

Questions, facts, readiness, the savings plan, the risk profile and the
goal.
"""

from typing import Any

from pydantic import Field

from app.core.errors import ToolError
from app.core.profile import Debt, Goal, Profile, RiskResult
from app.core.reference import Question
from app.core.types import IncomeStability, Stage, to_money
from app.engine.readiness import DebtLine, assess_readiness
from app.engine.savings import build_savings_plan
from app.engine.scoring import (
    AgeBandScore,
    HorizonBand,
    age_score,
    capacity_score,
    horizon_cap,
    risk_profile,
    tolerance_score,
)
from app.store import account
from app.tools.allocation import history_extremes
from app.tools.base import Input, NoArgs, Output
from app.tools.cards import (
    Chip,
    GoalCard,
    PauseCard,
    PlanStepView,
    QuestionCard,
    ReadinessCard,
    RiskBadgeCard,
    SavingsPlanCard,
    WhyLine,
)
from app.tools.context import ToolContext

# --- questions


def _answered(profile: Profile, q: Question) -> bool:
    if q.field.startswith("tolerance_answers."):
        return q.field.split(".", 1)[1] in profile.tolerance_answers
    return getattr(profile, q.field) is not None


def stage_questions(ctx: ToolContext, stage: Stage) -> list[Question]:
    """Return the questions asked in a stage, in order."""
    return [q for q in ctx.ref.questionnaire.questions if q.stage == stage]


def next_question(ctx: ToolContext) -> QuestionCard | None:
    """Return the first unanswered question of the current stage."""
    questions = stage_questions(ctx, ctx.session.stage)
    for i, q in enumerate(questions):
        if not _answered(ctx.session.profile, q):
            return QuestionCard(
                question_id=q.id,
                prompt=q.prompt,
                why=q.why,
                kind=q.kind,
                chips=[Chip(label=o.label, value=o.value) for o in q.options],
                step=i + 1,
                of=len(questions),
            )
    return None


def stage_complete(ctx: ToolContext) -> bool:
    """Return whether the current stage's questions are all answered."""
    return next_question(ctx) is None


def _coerce(q: Question, value: Any) -> Any:  # noqa: ANN401 (depends on the question kind)
    """Return the value in the profile's type, or raise ValueError."""
    if q.kind == "choice":
        allowed = [o.value for o in q.options]
        if value not in allowed:
            raise ValueError(f"choose one of {allowed}")
        return value
    if q.kind == "debts":
        return tuple(Debt.model_validate(d) for d in value)
    number = float(value)
    if number < (q.min or 0) or (q.max is not None and number > q.max):
        raise ValueError("that number is out of range")
    return int(number) if q.kind == "number" else number


def _with_answer(profile: Profile, q: Question, value: Any) -> Profile:  # noqa: ANN401
    if q.field.startswith("tolerance_answers."):
        key = q.field.split(".", 1)[1]
        return profile.model_copy(
            update={"tolerance_answers": {**profile.tolerance_answers, key: value}}
        )
    if q.field == "income_stability":
        value = IncomeStability(value)
    return Profile.model_validate({**profile.model_dump(), q.field: value})


class AnswerQuestionIn(Input):
    """A tapped chip or a typed answer to one question."""

    question_id: str = Field(max_length=40)
    value: Any = Field(description="The chip value, a number, or a list of debts")


class AnswerQuestionOut(Output):
    """What was recorded and whether the stage is finished."""

    recorded: str
    stage_complete: bool


def answer_question(ctx: ToolContext, args: AnswerQuestionIn) -> AnswerQuestionOut | ToolError:
    """Record the answer to one question of the current stage."""
    q = next(
        (x for x in stage_questions(ctx, ctx.session.stage) if x.id == args.question_id), None
    )
    if q is None:
        return ToolError(
            code="unknown_question", message="That question isn't asked at this step."
        )
    try:
        ctx.session.profile = _with_answer(ctx.session.profile, q, _coerce(q, args.value))
    except (ValueError, TypeError) as e:
        return ToolError(code="invalid_answer", message=f"I couldn't use that answer: {e}.")
    if ctx.session.stage == Stage.ONBOARD and stage_complete(ctx):
        ctx.session.stage = Stage.READINESS
        return AnswerQuestionOut(recorded=q.id, stage_complete=True)
    return AnswerQuestionOut(recorded=q.id, stage_complete=stage_complete(ctx))


class UpdateProfileIn(Input):
    """Facts the client stated themselves; omit anything unsaid."""

    age: int | None = Field(default=None, ge=18, le=100)
    monthly_income_usd: float | None = Field(default=None, ge=0, le=10_000_000)
    monthly_expenses_usd: float | None = Field(default=None, ge=0, le=10_000_000)
    liquid_savings_usd: float | None = Field(default=None, ge=0, le=100_000_000)
    debts: list[Debt] | None = Field(default=None, max_length=10)
    income_stability: IncomeStability | None = None
    dependants: int | None = Field(default=None, ge=0, le=20)


class UpdateProfileOut(Output):
    """Which facts were saved and which are still missing."""

    updated: list[str]
    missing: list[str]


def update_profile(ctx: ToolContext, args: UpdateProfileIn) -> UpdateProfileOut:
    """Save facts the client clearly stated, never guessed ones."""
    given = args.model_dump(exclude_none=True)
    if "debts" in given:
        given["debts"] = tuple(args.debts or ())
    ctx.session.profile = Profile.model_validate({**ctx.session.profile.model_dump(), **given})
    if ctx.session.stage == Stage.ONBOARD and ctx.session.profile.age is not None:
        ctx.session.stage = Stage.READINESS
    missing = [
        q.id
        for q in stage_questions(ctx, ctx.session.stage)
        if not _answered(ctx.session.profile, q)
    ]
    return UpdateProfileOut(updated=sorted(given), missing=missing)


# --- readiness and the savings plan


class ReadinessOut(Output):
    """The money health check."""

    ready: bool
    emergency_months: float
    investable_monthly_usd: float
    failed_rule_ids: list[str]


def _debt_lines(profile: Profile) -> list[DebtLine]:
    return [DebtLine(d.kind, d.balance_usd, d.apr_pct) for d in profile.debts or ()]


def _readiness(ctx: ToolContext) -> Any:  # noqa: ANN401 (engine Readiness)
    p, rules = ctx.session.profile, ctx.ref.rules
    return assess_readiness(
        monthly_income_usd=p.monthly_income_usd or 0,
        monthly_expenses_usd=p.monthly_expenses_usd or 0,
        liquid_savings_usd=p.liquid_savings_usd or 0,
        debts=_debt_lines(p),
        min_emergency_months=rules.ready_01.min_emergency_months,
        max_apr_pct=rules.ready_02.max_apr_pct,
    )


def assess_readiness_tool(ctx: ToolContext, _: NoArgs) -> ReadinessOut | ToolError:
    """Check the emergency fund and expensive debt before investing."""
    missing = [
        q.id
        for q in stage_questions(ctx, Stage.READINESS)
        if not _answered(ctx.session.profile, q)
    ]
    if missing:
        return ToolError(code="missing_answers", message=f"I still need: {', '.join(missing)}.")
    r = _readiness(ctx)
    rules = ctx.ref.rules
    reasons = []
    if "READY-02" in r.failed_rule_ids:
        worst = max(r.high_apr_debts, key=lambda d: d.apr_pct)
        reasons.append(
            WhyLine(
                rule_id="READY-02",
                text=f"Your {worst.kind.replace('_', ' ')} charges {worst.apr_pct:g}% a year. "
                f"Paying it off is like earning {worst.apr_pct:g}%, "
                "more than funds usually return.",
            )
        )
    if "READY-01" in r.failed_rule_ids:
        reasons.append(
            WhyLine(
                rule_id="READY-01",
                text=f"Your savings cover {r.emergency_months:.1f} months of costs. A safety "
                f"cushion of {rules.ready_01.min_emergency_months:g} months comes first.",
            )
        )
    ctx.cards.append(
        ReadinessCard(
            ready=r.ready,
            emergency_months=round(min(r.emergency_months, 99.0), 1),
            investable_monthly_usd=r.investable_monthly_usd,
            reasons=reasons,
        )
    )
    ctx.session.stage = Stage.PROFILE if r.ready else Stage.SAVINGS_PLAN
    return ReadinessOut(
        ready=r.ready,
        emergency_months=round(min(r.emergency_months, 99.0), 1),
        investable_monthly_usd=r.investable_monthly_usd,
        failed_rule_ids=list(r.failed_rule_ids),
    )


_STEP_TITLES = {
    "save_buffer": "Keep a small cash buffer",
    "pay_debt": "Pay off your {kind}",
    "build_emergency_fund": "Build your safety cushion",
}


class SavingsPlanOut(Output):
    """The steps and when the client could be ready."""

    steps: list[dict[str, Any]]
    months_to_ready: int | None


def _month_plus(ctx: ToolContext, months: int) -> str:
    y, m = int(ctx.session.sim_month[:4]), int(ctx.session.sim_month[5:])
    total = y * 12 + (m - 1) + months
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


def build_savings_plan_tool(ctx: ToolContext, _: NoArgs) -> SavingsPlanOut:
    """Build the "not yet" plan: buffer, debt, then savings."""
    r, p, rules = _readiness(ctx), ctx.session.profile, ctx.ref.rules
    plan = build_savings_plan(
        monthly_surplus_usd=r.investable_monthly_usd,
        liquid_savings_usd=p.liquid_savings_usd or 0,
        monthly_expenses_usd=p.monthly_expenses_usd or 0,
        expensive_debts=list(r.high_apr_debts),
        min_emergency_months=rules.ready_01.min_emergency_months,
        starter_buffer_usd=rules.ready_01.starter_buffer_usd,
    )
    views = [
        PlanStepView(
            action=s.action,
            title=_STEP_TITLES[s.action].format(kind=(s.debt_kind or "").replace("_", " ")),
            monthly_usd=s.monthly_usd,
            months=s.months,
            target_usd=s.target_usd,
            interest_usd=s.interest_usd,
        )
        for s in plan.steps
    ]
    ready_month = None if plan.months_to_ready is None else _month_plus(ctx, plan.months_to_ready)
    ctx.cards.append(
        SavingsPlanCard(steps=views, months_to_ready=plan.months_to_ready, ready_month=ready_month)
    )
    if plan.months_to_ready is None:
        ctx.cards.append(
            PauseCard(
                rule_id="READY-01",
                title="Let's find some room first",
                text="Right now nothing is left over each month. Lowering a cost or raising "
                "income by even $50 a month gives us a starting point.",
            )
        )
    return SavingsPlanOut(
        steps=[v.model_dump() for v in views], months_to_ready=plan.months_to_ready
    )


# --- risk profile


_LIMITED_BY_TEXT = {
    "tolerance": "how much ups and downs you said you're comfortable with",
    "capacity": "how much loss you could afford right now",
    "horizon": "how soon you need the money",
}


class RiskOut(Output):
    """The scored profile."""

    client_class: str
    tolerance: int
    capacity: int
    limited_by: str


def score_risk_profile(ctx: ToolContext, _: NoArgs) -> RiskOut | ToolError:
    """Score tolerance and capacity; the lower one sets the class."""
    p, q = ctx.session.profile, ctx.ref.questionnaire
    missing = [x.id for x in stage_questions(ctx, Stage.PROFILE) if not _answered(p, x)]
    if missing or p.age is None:
        return ToolError(code="missing_answers", message=f"I still need: {', '.join(missing)}.")
    scored = {x.id: x for x in q.questions if x.scale is not None}

    def score(question_id: str, value: Any) -> int:  # noqa: ANN401
        option = next(o for o in scored[question_id].options if o.value == value)
        assert option.score is not None  # noqa: S101 (validated in test_reference)
        return option.score

    tolerance = tolerance_score(
        [score(k, v) for k, v in p.tolerance_answers.items() if k in scored]
    )
    capacity = capacity_score(
        [
            age_score(p.age, [AgeBandScore(b.under, b.score) for b in q.capacity_by_age]),
            score("income_stability", p.income_stability),
            score("dependants", p.dependants),
            score("loss_capacity", p.loss_capacity),
        ]
    )
    result = risk_profile(tolerance, capacity, cap=None)
    ctx.session.profile = p.model_copy(
        update={
            "risk": RiskResult(
                tolerance=tolerance,
                capacity=capacity,
                final_class=result.final_class,
                limited_by=result.limited_by,
            )
        }
    )
    portfolio = ctx.ref.portfolios[result.final_class]
    worst, best = history_extremes(ctx, dict(portfolio.weights))
    ctx.cards.append(
        RiskBadgeCard(
            client_class=str(result.final_class),
            label=portfolio.label,
            summary=portfolio.summary,
            tolerance=tolerance,
            capacity=capacity,
            horizon_cap=None,
            limited_by=result.limited_by,
            why=[
                WhyLine(
                    rule_id=None,
                    text=f"Your class is set by {_LIMITED_BY_TEXT[result.limited_by]}.",
                ),
                WhyLine(
                    rule_id="SUIT-01",
                    text=f"You'll only see funds rated R{int(result.final_class)} or lower.",
                ),
            ],
            worst_12m_pct=round(worst * 100, 1),
            best_12m_pct=round(best * 100, 1),
        )
    )
    ctx.session.stage = Stage.GOAL
    return RiskOut(
        client_class=str(result.final_class),
        tolerance=tolerance,
        capacity=capacity,
        limited_by=result.limited_by,
    )


# --- goal


class SetGoalIn(Input):
    """The client's goal, in their numbers."""

    name: str = Field(max_length=60)
    target_usd: float = Field(gt=0, le=100_000_000)
    horizon_years: float = Field(gt=0, le=60)
    lump_sum_usd: float = Field(ge=0, le=10_000_000)
    monthly_usd: float = Field(ge=0, le=1_000_000)


class SetGoalOut(Output):
    """The goal and the class after the horizon cap."""

    client_class: str
    capped_by_horizon: bool
    deposited_usd: float


def set_goal(ctx: ToolContext, args: SetGoalIn) -> SetGoalOut | ToolError:
    """Save the goal, apply HOR-01 and fund the practice account."""
    p = ctx.session.profile
    if p.risk is None:
        return ToolError(code="no_profile", message="Let's finish your risk questions first.")
    bands = [HorizonBand(c.under_years, c.max_class) for c in ctx.ref.rules.hor_01.caps]
    cap = horizon_cap(args.horizon_years, bands)
    result = risk_profile(p.risk.tolerance, p.risk.capacity, cap)
    risk = p.risk.model_copy(
        update={
            "horizon_cap": cap,
            "final_class": result.final_class,
            "limited_by": result.limited_by,
        }
    )
    ctx.session.profile = p.model_copy(update={"goal": Goal(**args.model_dump()), "risk": risk})
    ctx.__dict__.pop("client_class", None)  # the cached class may have changed
    deposit = to_money(args.lump_sum_usd)
    account.set_cash(ctx.con, ctx.session.id, deposit)
    capped = cap is not None and result.limited_by == "horizon"
    ctx.cards.append(
        GoalCard(
            name=args.name,
            target_usd=args.target_usd,
            horizon_years=args.horizon_years,
            lump_sum_usd=args.lump_sum_usd,
            monthly_usd=args.monthly_usd,
            client_class=str(result.final_class),
            capped=capped,
        )
    )
    ctx.session.stage = Stage.PROPOSE
    return SetGoalOut(
        client_class=str(result.final_class),
        capped_by_horizon=capped,
        deposited_usd=float(deposit),
    )
