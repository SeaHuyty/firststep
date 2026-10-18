"""One conversation turn: guard, act, word the reply, filter, save.

A chip or button (`action`) runs its tool directly. Free text goes to
the LLM, which sees only the current stage's tools and never a Tier 2
tool, so it can propose but never execute. Both paths go through the
executor (policy check and audit log) and the same deterministic
follow-ups.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from pydantic_ai import Agent, RunContext, Tool
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)
from pydantic_ai.models import Model
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import UsageLimits

from app.agent import copy, executor, flow, guards, prompts
from app.agent.executor import Outcome
from app.agent.services import Services
from app.core.types import Stage
from app.store import sessions
from app.tools.cards import AllocationCard, Card, ConfirmCard, ProjectionCard, QuestionCard
from app.tools.registry import TOOLS, ToolSpec

logger = logging.getLogger(__name__)

HISTORY_MESSAGES = 10
MAX_TOOL_CALLS = 4
# A whole LLM turn, fallbacks included, must finish well inside the web
# proxy's limit (next.config.ts) so the person always gets an answer.
LLM_TURN_TIMEOUT_S = 45
REWRITE_TIMEOUT_S = 15
TIMEOUT_REPLY = "Sorry, Sprout didn't answer in time. Your answers are saved. Try again."
ERROR_REPLY = (
    "Sorry, Sprout couldn't reach its model just now. Your answers are saved. Try again, or "
    "use the buttons."
)


@dataclass
class TurnDeps:
    """What the LLM's tool wrappers need."""

    services: Services
    session_id: str
    outcomes: list[Outcome] = field(default_factory=list)


@dataclass
class TurnResult:
    """Everything the UI shows after a turn."""

    reply: str
    cards: list[Card]
    stage: Stage
    steps: list[str]
    pending_confirmation: str | None
    tokens: int = 0
    latency_ms: int = 0


def _llm_tool(spec: ToolSpec) -> Tool[TurnDeps]:
    """Wrap a tool so the model's call goes through the executor."""

    def call(ctx: RunContext[TurnDeps], args: Any) -> dict[str, Any]:  # noqa: ANN401
        deps = ctx.deps
        outcome = executor.run(
            deps.services, deps.session_id, spec.name, args.model_dump(), actor="llm"
        )
        deps.outcomes.append(outcome)
        chained = flow.follow_up(deps.services, deps.session_id, outcome)
        deps.outcomes.extend(chained)
        result = outcome.for_llm()
        if chained:
            result["then"] = [{c.tool: c.for_llm()} for c in chained]
        return result

    call.__annotations__ = {
        "ctx": RunContext[TurnDeps],
        "args": spec.input_model,
        "return": dict[str, Any],
    }
    return Tool(call, name=spec.name, description=spec.description, takes_ctx=True)


def llm_tools(services: Services, stage: Stage) -> list[Tool[TurnDeps]]:
    """Return the tools the model may call now (never Tier 2)."""
    tiers = services.ref.rules.tiers.tier_of
    allowed = services.ref.rules.stage_01.allowed.get(stage, ())
    return [_llm_tool(TOOLS[name]) for name in allowed if tiers[name] != 2 and name in TOOLS]


def _history(services: Services, session_id: str) -> list[ModelMessage]:
    with services.store.tx() as con:
        rows = sessions.messages(con, session_id, limit=HISTORY_MESSAGES)
    return [
        ModelRequest(parts=[UserPromptPart(content=m.text)])
        if m.role == "user"
        else ModelResponse(parts=[TextPart(content=m.text)])
        for m in rows
        if m.text
    ]


async def _ask_llm(
    services: Services,
    model: Model,
    settings: ModelSettings,
    session_id: str,
    text: str,
    injection: bool,
) -> tuple[str, list[Outcome], int]:
    with services.store.tx() as con:
        row = sessions.get(con, session_id)
    if row is None:
        raise KeyError(session_id)
    deps = TurnDeps(services, session_id)
    agent: Agent[TurnDeps, str] = Agent(
        model,
        deps_type=TurnDeps,
        instructions=prompts.instructions(row.stage, row.profile, row.sim_month, injection),
        tools=llm_tools(services, row.stage),
        model_settings=settings,
    )
    history = _history(services, session_id)
    result = await agent.run(
        text,
        message_history=history,
        deps=deps,
        usage_limits=UsageLimits(
            request_limit=MAX_TOOL_CALLS + 2, tool_calls_limit=MAX_TOOL_CALLS
        ),
    )
    usage = result.usage
    return (
        result.output.strip(),
        deps.outcomes,
        (usage.input_tokens or 0) + (usage.output_tokens or 0),
    )


async def _filtered(
    services: Services, model: Model, settings: ModelSettings, reply: str
) -> tuple[str, list[str]]:
    """Return a reply passing LANG-*, rewriting it once if needed."""
    hits = guards.check_output(services.policy, reply)
    if not hits:
        return reply, []
    rewriter: Agent[None, str] = Agent(
        model, model_settings=settings, instructions=prompts.REWRITE
    )
    try:
        run = rewriter.run(f"Rewrite without {', '.join(hits)}: {reply}")
        rewritten = (await asyncio.wait_for(run, REWRITE_TIMEOUT_S)).output
    except Exception:  # any provider failure falls back to the safe text
        rewritten = ""
    if rewritten and not guards.check_output(services.policy, rewritten):
        return rewritten.strip(), hits
    return guards.SAFE_FALLBACK, hits


def _pending_confirmation(cards: list[Card]) -> str | None:
    confirms = [c for c in cards if isinstance(c, ConfirmCard)]
    return confirms[-1].proposal_id if confirms else None


def _action_label(label: object) -> str | None:
    """Return a chip's words to keep as the user's message, or None.

    The label comes from the browser, and later turns send stored
    messages to the LLM as history, so it gets the same check as typed
    text. A label that looks like an injection is dropped: real chips
    never do.
    """
    if not isinstance(label, str) or not label.strip():
        return None
    checked = guards.check_input(label.strip())
    return None if checked.injection else checked.text


async def take_turn(
    services: Services,
    model: Model,
    settings: ModelSettings,
    session_id: str,
    *,
    text: str | None = None,
    action: dict[str, Any] | None = None,
) -> TurnResult:
    """Run one turn and return what to show."""
    started = time.perf_counter()
    log = services.audit(session_id)
    tokens = 0
    if action is not None:
        tool = str(action.get("tool", ""))
        user_text = _action_label(action.get("label"))
        said = {"label": user_text} if user_text else {}
        log.append("user_msg", "user", {"action": tool, **said})
        first = executor.run(
            services, session_id, tool, dict(action.get("args") or {}), actor="user"
        )
        outcomes = [first, *flow.follow_up(services, session_id, first)]
        with services.store.tx() as con:
            row = sessions.get(con, session_id)
        reply = copy.reply_for(outcomes, row.stage if row else Stage.ONBOARD)
        hits: list[str] = []
    else:
        checked = guards.check_input(text or "")
        user_text = checked.text
        log.append("user_msg", "user", {"text": checked.text})
        if checked.injection or checked.masked:
            log.append(
                "guard", "system", {"injection": checked.injection, "masked": list(checked.masked)}
            )
        try:
            reply, outcomes, tokens = await asyncio.wait_for(
                _ask_llm(services, model, settings, session_id, checked.text, checked.injection),
                LLM_TURN_TIMEOUT_S,
            )
        except TimeoutError:
            logger.warning(
                "LLM turn took over %ss; answered with the timeout reply", LLM_TURN_TIMEOUT_S
            )
            reply, outcomes = TIMEOUT_REPLY, []
        except Exception as e:  # provider failure: keep the session, say so plainly
            logger.warning("LLM turn failed: %s: %s", type(e).__name__, str(e)[:300])
            reply, outcomes = ERROR_REPLY, []
        reply, hits = await _filtered(
            services, model, settings, reply or copy.reply_for(outcomes, Stage.ONBOARD)
        )

    cards: list[Card] = [c for o in outcomes for c in o.cards]
    question = flow.pending_question(services, session_id)
    if question is not None and not any(isinstance(c, QuestionCard) for c in cards):
        cards.append(question)
    if any(isinstance(c, AllocationCard | ProjectionCard | ConfirmCard) for c in cards):
        reply = guards.with_disclosure(reply)

    latency = int((time.perf_counter() - started) * 1000)
    log.append(
        "reply",
        "llm" if action is None else "system",
        {
            "text": reply,
            "cards": [c.type for c in cards],
            "lang_hits": ",".join(hits),
            "tokens": tokens,
            "latency_ms": latency,
        },
    )
    with services.store.tx() as con:
        now = services.clock().isoformat(timespec="seconds")
        if user_text is not None:
            sessions.add_message(con, session_id, "user", user_text, [], now)
        sessions.add_message(
            con, session_id, "sprout", reply, [c.model_dump(mode="json") for c in cards], now
        )
        sessions.update(con, session_id, now=now, audit_head=log.head())
        row = sessions.get(con, session_id)
    return TurnResult(
        reply=reply,
        cards=cards,
        stage=row.stage if row else Stage.ONBOARD,
        steps=[o.tool for o in outcomes],
        pending_confirmation=_pending_confirmation(cards),
        tokens=tokens,
        latency_ms=latency,
    )
