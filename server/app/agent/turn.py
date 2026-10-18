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

from pydantic_ai import Agent, RunContext, Tool, UsageLimitExceeded
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
from app.core.types import FAMILY_OF, Stage
from app.store import account, sessions
from app.tools.cards import AllocationCard, Card, ConfirmCard, ProjectionCard, QuestionCard
from app.tools.registry import TOOLS, ToolSpec

logger = logging.getLogger(__name__)

HISTORY_MESSAGES = 10
MAX_TOOL_CALLS = 4
# A malformed call goes back to the model with the error; free models
# often need a second or third try.
TOOL_RETRIES = 3
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
    return Tool(
        call,
        name=spec.name,
        description=spec.description,
        takes_ctx=True,
        max_retries=TOOL_RETRIES,
    )


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


def _context(services: Services, session_id: str, row: sessions.SessionRow) -> list[str]:
    """Return the funds, plan and question the model must name right."""
    ref = services.ref
    risk = row.profile.risk
    cap = ref.rules.suit_01.max_rating_for_class[risk.final_class] if risk else None
    funds = [
        f"- {p.id}: {p.name} ({FAMILY_OF[p.asset_class].value}, {p.risk_rating}, "
        f"${p.ter_pct * 10:.2f} a year per $1,000)"
        + (" above the client's level" if cap is not None and p.risk_rating > cap else "")
        for p in ref.products.values()
    ]
    lines = ["FUNDS:", *funds]
    with services.store.tx() as con:
        plan = account.latest_proposal(con, session_id, "allocation")
    if plan is not None:
        weights = plan.contents.get("weights", {})
        mix = ", ".join(f"{pid} {w:g}%" for pid, w in weights.items())
        lines.append(f"CURRENT PLAN: {mix}")
    question = flow.pending_question(services, session_id)
    if question is not None:
        chips = "; ".join(f"{c.label} = {c.value!r}" for c in question.chips)
        lines.append(
            f"QUESTION NOW: question_id={question.question_id} ({question.kind}): "
            f"{question.prompt}" + (f" Answers: {chips}." if chips else "")
        )
    return lines


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
        instructions=prompts.instructions(
            row.stage, row.profile, row.sim_month, injection, _context(services, session_id, row)
        ),
        tools=llm_tools(services, row.stage),
        model_settings=settings,
    )
    history = _history(services, session_id)
    try:
        result = await agent.run(
            text,
            message_history=history,
            deps=deps,
            usage_limits=UsageLimits(
                request_limit=MAX_TOOL_CALLS + TOOL_RETRIES + 2, tool_calls_limit=MAX_TOOL_CALLS
            ),
        )
    except UsageLimitExceeded:
        if not deps.outcomes:
            raise
        # The calls that ran are done and logged: say what they did.
        logger.warning(
            "LLM turn hit its usage limit; replying from %d tool calls", len(deps.outcomes)
        )
        with services.store.tx() as con:
            now = sessions.get(con, session_id)
        stage = now.stage if now else row.stage
        return copy.reply_for(deps.outcomes, stage), deps.outcomes, 0
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
        # The whole turn, fallbacks included, ends inside the web
        # proxy's limit (next.config.ts): there is always an answer.
        timeout_s = services.settings.llm_turn_timeout_s
        try:
            reply, outcomes, tokens = await asyncio.wait_for(
                _ask_llm(services, model, settings, session_id, checked.text, checked.injection),
                timeout_s,
            )
        except TimeoutError:
            logger.warning("LLM turn took over %ss; answered with the timeout reply", timeout_s)
            reply, outcomes = TIMEOUT_REPLY, []
        except Exception as e:  # provider failure: keep the session, say so plainly
            # A fallback chain fails as a group: log each reason.
            parts = e.exceptions if isinstance(e, BaseExceptionGroup) else [e]
            reasons = "; ".join(f"{type(x).__name__}: {str(x)[:160]}" for x in parts)
            logger.warning("LLM turn failed: %s", reasons)
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
