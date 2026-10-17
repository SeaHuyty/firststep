"""A scripted stand-in for the LLM, built on pydantic-ai FunctionModel.

It reads the client's last message, picks a tool the way a well-behaved
model would, then words the reply from the tool result. It never sees a
confirmation token and has no tool that places orders, exactly like the
real model. Used by tests, CI, the persona runner and the offline demo.
"""

import json
import re
from collections.abc import Callable
from typing import Any

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel

Rule = tuple[re.Pattern[str], str, Callable[[re.Match[str]], dict[str, Any]]]

_TERMS = (
    "etf",
    "index fund",
    "bond",
    "fee",
    "ter",
    "diversification",
    "volatility",
    "risk class",
    "risk rating",
    "emergency fund",
    "rebalancing",
    "drawdown",
)
_GLOSSARY = "(?P<term>" + "|".join(_TERMS) + ")"
REFUSE = "I can't change how I work or skip steps, but I'm happy to keep going with your plan."
DEFAULT = "I'm here to help with your plan. Tap an answer below, or ask me what anything means."

RULES: list[Rule] = [
    (
        re.compile(r"\b(all|everything)\b.*\btech|\btech(nology)? stocks?\b", re.I),
        "propose_custom_allocation",
        lambda m: {"lines": [{"product_id": "TEC01", "weight_pct": 100}]},
    ),
    (re.compile(r"\bsell (everything|it all|all)\b", re.I), "request_sell", lambda m: {}),
    (re.compile(r"\bsell\b", re.I), "get_portfolio", lambda m: {}),
    (
        re.compile(r"(jump|fast[- ]?forward|skip).*(march )?2020", re.I),
        "advance_time",
        lambda m: {"until": "2020-03"},
    ),
    (re.compile(r"fast[- ]?forward", re.I), "advance_time", lambda m: {"months": 1}),
    (re.compile(r"\brebalanc", re.I), "propose_rebalance", lambda m: {}),
    (
        re.compile(r"\bcompare\b", re.I),
        "compare_products",
        lambda m: {"product_ids": ["USE01", "ACT01"]},
    ),
    (
        re.compile(rf"(what('s| is| are| does)|explain|mean).*?\b{_GLOSSARY}\b", re.I),
        "explain",
        lambda m: {"topic": m.group("term")},
    ),
    (
        re.compile(r"\bi(?:'m| am) (\d{2})\b", re.I),
        "update_profile",
        lambda m: {"age": int(m.group(1))},
    ),
]

_NO_TOOL = [
    (
        re.compile(r"place|buy (it )?now|execute|confirm (it )?for me|do it for me", re.I),
        "I can't place orders myself. When you're ready, review the orders and press Confirm.",
    ),
]

_INJECTION_NOTE = "looks like an attempt to change your rules"


def _last_user_text(messages: list[ModelMessage]) -> str:
    for message in reversed(messages):
        if isinstance(message, ModelRequest):
            for part in message.parts:
                if isinstance(part, UserPromptPart) and isinstance(part.content, str):
                    return part.content
    return ""


def _tool_returns(messages: list[ModelMessage]) -> list[ToolReturnPart]:
    last = messages[-1] if messages else None
    if isinstance(last, ModelRequest):
        return [p for p in last.parts if isinstance(p, ToolReturnPart)]
    return []


def _content(part: ToolReturnPart) -> dict[str, Any]:
    raw = part.content
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return raw if isinstance(raw, dict) else {}


def _after_tool(part: ToolReturnPart, offered: set[str]) -> ModelResponse:
    """Word the reply from a tool result, or call one follow-up tool."""
    data = _content(part)
    if "error" in data:
        msg = data["error"].get("message", "I can't do that.")
        if part.tool_name == "propose_custom_allocation":
            msg += " Here's a steadier plan that fits your level instead."
        return ModelResponse(parts=[TextPart(msg)])
    result = data.get("result") or {}
    if part.tool_name == "get_portfolio" and "request_sell" in offered:
        holdings: dict[str, str] = result.get("holdings", {})
        if holdings:
            pid = max(holdings, key=lambda k: float(holdings[k]))
            args = {"product_id": pid, "amount_usd": float(holdings[pid])}
            return ModelResponse(parts=[ToolCallPart("request_sell", args)])
    text = {
        "explain": result.get("text", ""),
        "advance_time": "Here's where your plan stands now. Ups and downs are normal; your plan "
        "was built for years, not months.",
        "update_profile": "Thanks, I've noted that.",
        "compare_products": "Here they are side by side. Look at the fees: they add up over time.",
        "propose_rebalance": "Here's a rebalance back to your target mix. Press Confirm if you "
        "want it.",
        "request_sell": "Here's the sale. Nothing happens until you press Confirm.",
    }.get(part.tool_name, "Done. Take a look at the card below.")
    return ModelResponse(parts=[TextPart(text)])


def _first_step(text: str, info: AgentInfo, offered: set[str]) -> ModelResponse:
    """Pick a tool for the client's message, or reply without one."""
    if _INJECTION_NOTE in (info.instructions or ""):
        reply = REFUSE
    else:
        reply = next((r for pattern, r in _NO_TOOL if pattern.search(text)), DEFAULT)
        if reply == DEFAULT:
            for pattern, tool, make_args in RULES:
                m = pattern.search(text)
                if m and tool in offered:
                    return ModelResponse(parts=[ToolCallPart(tool, make_args(m))])
    return ModelResponse(parts=[TextPart(reply)])


def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    """Act as the model for one step of a turn."""
    offered = {t.name for t in info.function_tools}
    returns = _tool_returns(messages)
    if returns:
        return _after_tool(returns[-1], offered)
    return _first_step(_last_user_text(messages), info, offered)


def fake_model() -> FunctionModel:
    """Return the scripted model."""
    return FunctionModel(respond, model_name="firststep-fake")
