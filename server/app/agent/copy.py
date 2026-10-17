"""Sprout's fixed lines for chip and button turns (no LLM needed).

Voice rules from docs/standards/brand.md: calm, plain, honest about
risk, impact before reasoning, buttons say what happens.
"""

from app.agent.executor import Outcome
from app.core.types import Stage

WELCOME = (
    "Hi, I'm Sprout. I'll help you make a first investing plan, one step at a time. First I'll "
    "check whether now is a good time to invest, then how you feel about ups and downs, then "
    "your goal. Nothing happens without your OK, and you can ask me what anything means."
)

_BY_TOOL_OK = {
    "assess_readiness": (
        "Good news: you have a safety cushion and no expensive debt, so you're ready to start. "
        "Next, a few questions about how you feel about ups and downs."
    ),
    "build_savings_plan": (
        "Not yet, and here's why. Paying off expensive debt and building a safety cushion will "
        "do more for you right now than any fund. Here's a plan; I'll check in when you're ready."
    ),
    "score_risk_profile": (
        "Thanks. Here's your risk level. You'll only see funds that fit it. "
        "Now, what are you investing for?"
    ),
    "set_goal": "Got it. I've put $AMOUNT in your practice account. Here's a plan that fits.",
    "propose_allocation": "Here's a plan built from low-cost index funds that fit your level.",
    "project_outcomes": (
        "And here's a range of what could happen, from replaying past markets. It's not a "
        "prediction. When you're ready, review the orders."
    ),
    "prepare_orders": "Here's exactly what will happen. Nothing moves until you press Confirm.",
    "place_order": (
        "Done. Your orders are filled in the practice account. You can fast-forward time to see "
        "how the plan behaves."
    ),
    "advance_time": "Time has moved forward. Here's where your plan stands.",
    "propose_rebalance": "Here's a rebalance that brings your mix back to its target.",
    "request_sell": "Here's the sale. Nothing happens until you confirm.",
    "get_portfolio": "Here's your practice portfolio.",
    "check_drift": "Here's how far your mix is from its target.",
    "list_suitable_products": "These are the funds that fit your level.",
    "compare_products": "Here they are side by side. Fees are shown in dollars too.",
}


def _line(outcome: Outcome) -> str:
    line = _BY_TOOL_OK[outcome.tool]
    if outcome.tool == "set_goal" and outcome.output:
        line = line.replace("AMOUNT", f"{outcome.output['deposited_usd']:,.0f}")
    return line


def reply_for(outcomes: list[Outcome], stage: Stage) -> str:
    """Return Sprout's line for a turn that used no LLM."""
    for outcome in reversed(outcomes):
        if outcome.error is not None:
            return outcome.error.message
        if outcome.tool in _BY_TOOL_OK:
            return _line(outcome)
    # A plain answer needs no reply: the next question is the reply.
    return "" if stage in {Stage.ONBOARD, Stage.READINESS, Stage.PROFILE} else "Thanks."
