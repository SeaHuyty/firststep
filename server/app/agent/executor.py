"""One path for every tool call: validate, ask the guardian, run, log.

Chips, buttons and the LLM all call tools through `run`, so the same
policy checks and the same audit trail apply whoever asked. A refusal
comes back as data (a ToolError and a card), never as an exception.
"""

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import ValidationError

from app.agent.services import Services
from app.core.errors import ToolError
from app.policy.gate import check
from app.store import account, sessions
from app.tools.base import Input
from app.tools.broker import PlaceOrderIn
from app.tools.cards import Card, PauseCard, ReceiptCard, RefusalCard
from app.tools.context import SessionState, ToolContext
from app.tools.registry import TOOLS

Actor = Literal["user", "llm", "system"]

_PAUSE_RULES = {"READY-01", "READY-02", "COOL-01"}
_NEXT_STEP = {
    "SUIT-01": "Here's a plan that fits your level instead.",
    "CONC-01": "Spreading the money over several funds keeps one bad result from sinking it.",
    "LIM-01": "Try a smaller amount, or split it over two days.",
    "CONF-01": "Review the orders and press Confirm to go ahead.",
    "STAGE-01": "Let's finish this step first.",
}
_TITLES = {
    "SUIT-01": "That doesn't fit your risk level",
    "CONC-01": "That puts too much in one place",
    "LIM-01": "That's above the sandbox limit",
    "CONF-01": "This needs your confirmation",
    "STAGE-01": "Not at this step",
}


@dataclass
class Outcome:
    """What one tool call did."""

    tool: str
    actor: Actor
    output: dict[str, Any] | None = None
    error: ToolError | None = None
    cards: list[Card] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """Return whether the tool ran and succeeded."""
        return self.error is None

    def for_llm(self) -> dict[str, Any]:
        """Return what the model sees: the result or the refusal."""
        if self.error is not None:
            return {"error": self.error.model_dump()}
        return {"result": self.output}


def _redact(args: dict[str, Any]) -> dict[str, Any]:
    """Return args safe to log: tokens never reach the audit file."""
    return {k: ("[redacted]" if "token" in k else v) for k, v in args.items()}


def _refusal_card(rule_id: str, message: str) -> Card:
    if rule_id in _PAUSE_RULES:
        return PauseCard(rule_id=rule_id, title="Not yet, and here's why", text=message)
    return RefusalCard(
        rule_id=rule_id,
        title=_TITLES.get(rule_id, "I can't do that"),
        text=message,
        next_step=_NEXT_STEP.get(rule_id, ""),
    )


def run(
    services: Services, session_id: str, tool: str, raw_args: dict[str, Any], actor: Actor
) -> Outcome:
    """Run one tool for a session inside one transaction."""
    log = services.audit(session_id)
    log.append("tool_call", actor, {"tool": tool, "args": _redact(raw_args)})
    outcome = Outcome(tool=tool, actor=actor)
    with services.store.tx() as con:
        row = sessions.get(con, session_id)
        if row is None:
            raise KeyError(session_id)
        ctx = ToolContext(
            ref=services.ref,
            prices=services.prices,
            con=con,
            session=SessionState(
                row.id, row.persona, row.stage, row.profile, row.sim_month, row.sim_offset_hours
            ),
            now=services.clock(),
        )
        spec = TOOLS.get(tool)
        if spec is None:
            outcome.error = ToolError(
                code="unknown_tool", message=f"There is no tool called {tool}."
            )
        else:
            try:
                args = spec.input_model.model_validate(raw_args)
            except ValidationError as e:
                outcome.error = ToolError(
                    code="invalid_args",
                    message=f"Those details didn't look right ({e.error_count()} problem(s)).",
                )
            else:
                _decide_and_run(services, ctx, tool, args, outcome)
        log.append(
            "tool_result",
            "system",
            {
                "tool": tool,
                "ok": outcome.ok,
                "error": None if outcome.error is None else outcome.error.model_dump(),
                "stage": ctx.session.stage.value,
            },
        )
        head = log.head()
        outcome.cards = [
            c.model_copy(update={"audit_head": head}) if isinstance(c, ReceiptCard) else c
            for c in ctx.cards
        ]
        sessions.update(
            con,
            session_id,
            now=ctx.iso_now(),
            stage=ctx.session.stage,
            profile=ctx.session.profile,
            sim_month=ctx.session.sim_month,
            sim_offset_hours=ctx.session.sim_offset_hours,
            audit_head=head,
        )
    return outcome


def _decide_and_run(
    services: Services, ctx: ToolContext, tool: str, args: Input, outcome: Outcome
) -> None:
    log = services.audit(ctx.session.id)
    decision = check(services.policy, tool, args, ctx)
    log.append(
        "policy",
        "system",
        {
            "tool": tool,
            "allowed": decision.allowed,
            "rule_id": decision.rule_id,
            "message": decision.message,
        },
    )
    if not decision.allowed:
        outcome.error = ToolError(
            code="blocked", rule_id=decision.rule_id, message=decision.message
        )
        ctx.cards.append(_refusal_card(decision.rule_id or "", decision.message))
        return
    if isinstance(args, PlaceOrderIn):
        claims = services.policy.signer.read(args.confirmation_token)
        assert claims is not None  # noqa: S101 (the gate just verified it)
        account.use_nonce(ctx.con, claims.nonce, args.proposal_id, ctx.iso_now())
    result = TOOLS[tool].fn(ctx, args)
    if isinstance(result, ToolError):
        outcome.error = result
        if result.rule_id and not any(isinstance(c, PauseCard) for c in ctx.cards):
            ctx.cards.append(_refusal_card(result.rule_id, result.message))
        return
    outcome.output = result.model_dump(mode="json")
    if tool == "place_order":
        log.append(
            "fill",
            "system",
            {"fills": outcome.output.get("fills", []), "cash_usd": outcome.output.get("cash_usd")},
        )
