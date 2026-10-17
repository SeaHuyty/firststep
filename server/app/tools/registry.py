"""Every tool by name: its input model, function and permission tier.

Tiers come from data/rules.yaml (`TIERS`), so the table judges read is
the one the code enforces; a test checks the two agree.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from app.core.errors import ToolError
from app.tools import allocation, broker, monitor, products, profile
from app.tools.base import Input, NoArgs
from app.tools.context import ToolContext

ToolFn = Callable[[ToolContext, Any], BaseModel | ToolError]


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """One tool the executor can run."""

    name: str
    input_model: type[Input]
    fn: ToolFn

    @property
    def description(self) -> str:
        """Return the docstring the LLM sees as the tool description."""
        return (self.fn.__doc__ or "").strip()


_ALL = (
    ToolSpec("answer_question", profile.AnswerQuestionIn, profile.answer_question),
    ToolSpec("update_profile", profile.UpdateProfileIn, profile.update_profile),
    ToolSpec("assess_readiness", NoArgs, profile.assess_readiness_tool),
    ToolSpec("build_savings_plan", NoArgs, profile.build_savings_plan_tool),
    ToolSpec("score_risk_profile", NoArgs, profile.score_risk_profile),
    ToolSpec("set_goal", profile.SetGoalIn, profile.set_goal),
    ToolSpec("list_suitable_products", products.ListProductsIn, products.list_suitable_products),
    ToolSpec("compare_products", products.CompareIn, products.compare_products),
    ToolSpec("explain", products.ExplainIn, products.explain),
    ToolSpec("propose_allocation", NoArgs, allocation.propose_allocation),
    ToolSpec(
        "propose_custom_allocation",
        allocation.ProposeCustomIn,
        allocation.propose_custom_allocation,
    ),
    ToolSpec("project_outcomes", NoArgs, allocation.project_outcomes_tool),
    ToolSpec("prepare_orders", NoArgs, broker.prepare_orders),
    ToolSpec("place_order", broker.PlaceOrderIn, broker.place_order),
    ToolSpec("propose_rebalance", NoArgs, broker.propose_rebalance),
    ToolSpec("request_sell", broker.RequestSellIn, broker.request_sell),
    ToolSpec("get_portfolio", NoArgs, monitor.get_portfolio),
    ToolSpec("advance_time", monitor.AdvanceIn, monitor.advance_time),
    ToolSpec("check_drift", NoArgs, monitor.check_drift),
)

TOOLS: dict[str, ToolSpec] = {t.name: t for t in _ALL}
