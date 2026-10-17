"""Deterministic next steps after a tool call (the hybrid design).

When an answer completes a stage, the next tool runs at once through the
same executor, so chip taps never depend on an LLM and every step is
still a policy-checked, logged tool call. The LLM path uses the same
follow-ups, so both paths reach the same states.
"""

from app.agent.executor import Outcome, run
from app.agent.services import Services
from app.core.types import Stage
from app.store import sessions
from app.tools.cards import QuestionCard
from app.tools.context import SessionState, ToolContext
from app.tools.profile import next_question

MAX_CHAIN = 6


def _state(services: Services, session_id: str) -> tuple[Stage, QuestionCard | None]:
    """Return the session's stage and its next unanswered question."""
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
        return row.stage, next_question(ctx)


def _next_tool(outcome: Outcome, stage: Stage, question: QuestionCard | None) -> str | None:
    """Return the tool that should follow, or None."""
    if not outcome.ok:
        refused = outcome.error.rule_id if outcome.error else None
        if outcome.tool == "propose_custom_allocation" and refused in {"SUIT-01", "CONC-01"}:
            return "propose_allocation"  # what, why, what instead
        return None
    answered = outcome.tool in {"answer_question", "update_profile"}
    follow = {
        "assess_readiness": "build_savings_plan" if stage == Stage.SAVINGS_PLAN else None,
        "set_goal": "propose_allocation",
        "propose_allocation": "project_outcomes",
        "propose_custom_allocation": "project_outcomes",
    }
    if answered and question is None:
        return {Stage.READINESS: "assess_readiness", Stage.PROFILE: "score_risk_profile"}.get(
            stage
        )
    return follow.get(outcome.tool)


def follow_up(services: Services, session_id: str, outcome: Outcome) -> list[Outcome]:
    """Run the tools that follow an outcome; return their outcomes."""
    chain: list[Outcome] = []
    current = outcome
    for _ in range(MAX_CHAIN):
        stage, question = _state(services, session_id)
        tool = _next_tool(current, stage, question)
        if tool is None:
            break
        current = run(services, session_id, tool, {}, actor="system")
        chain.append(current)
    return chain


def pending_question(services: Services, session_id: str) -> QuestionCard | None:
    """Return the next question to show under Sprout's reply, if any."""
    return _state(services, session_id)[1]
