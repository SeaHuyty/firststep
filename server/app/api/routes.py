"""HTTP routes: parse, call the agent, return. No business logic."""

import json
import secrets
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request

from app.agent.copy import WELCOME
from app.agent.services import Services
from app.agent.turn import TurnResult, take_turn
from app.api import schemas
from app.audit.verify import verify_lines
from app.core.types import FAMILY_OF, Stage
from app.store import account, sessions
from app.tools.cards import Card
from app.tools.context import SessionState, ToolContext
from app.tools.profile import first_question, next_question

router = APIRouter(prefix="/api")

DEFAULT_START = "2024-01"


def get_services(request: Request) -> Services:
    """Return the services built at start-up."""
    services: Services = request.app.state.services
    return services


ServicesDep = Annotated[Services, Depends(get_services)]


def _now(services: Services) -> str:
    return services.clock().isoformat(timespec="seconds")


def _persona(services: Services, key: str | None) -> schemas.PersonaHint | None:
    persona = services.ref.personas.personas.get(key or "")
    if persona is None:
        return None
    return schemas.PersonaHint(
        name=persona.name,
        tagline=persona.tagline,
        answers=persona.answers,
        goal=persona.goal.model_dump() if persona.goal else None,
        opening_line=persona.opening_line,
    )


def _view(services: Services, session_id: str) -> schemas.SessionView:
    with services.store.tx() as con:
        row = sessions.get(con, session_id)
        if row is None:
            raise HTTPException(404, "No such session.")
        messages = sessions.messages(con, session_id)
    return schemas.SessionView(
        id=row.id,
        persona=_persona(services, row.persona),
        stage=row.stage.value,
        sim_month=row.sim_month,
        messages=[schemas.Message(role=m.role, text=m.text, cards=m.cards) for m in messages],
    )


@router.get("/health")
def health(request: Request) -> schemas.Health:
    """Return a liveness flag and the LLM provider in use."""
    return schemas.Health(ok=True, llm=request.app.state.llm_provider)


@router.get("/catalog")
def catalog(services: ServicesDep) -> dict[str, Any]:
    """Return the shelf, glossary, rules, personas, first question."""
    ref = services.ref
    rules = ref.rules.model_dump(by_alias=True, mode="json")
    return {
        # Each fund with its family, for the fund library.
        "products": [
            {**p.model_dump(mode="json"), "family": FAMILY_OF[p.asset_class].value}
            for p in ref.products.values()
        ],
        # SUIT-01's matrix, so the library can label funds above a
        # level. The guardian still decides every proposal.
        "max_rating_for_class": rules["SUIT-01"]["max_rating_for_class"],
        "glossary": {k: t.model_dump() for k, t in ref.glossary.terms.items()},
        "sources": {k: s.model_dump() for k, s in ref.glossary.sources.items()},
        "rules": {
            k: {"title": v["title"], "description": v["description"]}
            for k, v in rules.items()
            if isinstance(v, dict) and "title" in v
        },
        "personas": {
            k: {"name": p.name, "tagline": p.tagline} for k, p in ref.personas.personas.items()
        },
        "first_question": first_question(ref).model_dump(mode="json"),
    }


@router.post("/sessions")
def create_session(body: schemas.NewSession, services: ServicesDep) -> schemas.SessionView:
    """Start a session and greet the user with the first question."""
    session_id = secrets.token_urlsafe(12)
    persona = services.ref.personas.personas.get(body.persona or "")
    log = services.audit(session_id)
    log.append("system", "system", {"event": "session_created", "persona": body.persona})
    with services.store.tx() as con:
        sessions.create(
            con,
            session_id=session_id,
            persona=body.persona,
            stage=Stage.ONBOARD,
            sim_month=persona.sim_start if persona else DEFAULT_START,
            audit_head=log.head(),
            now=_now(services),
        )
        row = sessions.get(con, session_id)
        assert row is not None  # noqa: S101 (just inserted)
        ctx = ToolContext(
            ref=services.ref,
            prices=services.prices,
            con=con,
            session=SessionState(row.id, row.persona, row.stage, row.profile, row.sim_month, 0.0),
            now=services.clock(),
        )
        first = next_question(ctx)
        cards: list[Card] = [first] if first else []
        sessions.add_message(
            con,
            session_id,
            "sprout",
            WELCOME,
            [c.model_dump(mode="json") for c in cards],
            _now(services),
        )
    return _view(services, session_id)


@router.get("/sessions/{session_id}")
def get_session(session_id: str, services: ServicesDep) -> schemas.SessionView:
    """Return a session so a refreshed page lands where it was."""
    return _view(services, session_id)


def _turn_out(result: TurnResult, services: Services, session_id: str) -> schemas.TurnOut:
    with services.store.tx() as con:
        row = sessions.get(con, session_id)
    return schemas.TurnOut(
        reply=result.reply,
        cards=result.cards,
        stage=result.stage.value,
        sim_month=row.sim_month if row else "",
        steps=result.steps,
        pending_confirmation=result.pending_confirmation,
    )


def _require(services: Services, session_id: str) -> None:
    with services.store.tx() as con:
        if sessions.get(con, session_id) is None:
            raise HTTPException(404, "No such session.")


@router.post("/sessions/{session_id}/turn")
async def turn(
    session_id: str, body: schemas.TurnIn, request: Request, services: ServicesDep
) -> schemas.TurnOut:
    """Run one turn: typed text (LLM) or a chip or button (direct)."""
    _require(services, session_id)
    result = await take_turn(
        services,
        request.app.state.model,
        request.app.state.model_settings,
        session_id,
        text=body.text,
        action=body.action.model_dump() if body.action else None,
    )
    return _turn_out(result, services, session_id)


@router.post("/sessions/{session_id}/confirm/{proposal_id}")
async def confirm(
    session_id: str, proposal_id: str, request: Request, services: ServicesDep
) -> schemas.TurnOut:
    """The Confirm button: mint a one-time token and place the orders.

    This is the only place a confirmation token is created, and it
    never leaves the server, so neither the browser script nor the LLM
    can produce one (CONF-01).
    """
    _require(services, session_id)
    with services.store.tx() as con:
        proposal = account.get_proposal(con, proposal_id)
    if proposal is None or proposal.session_id != session_id or proposal.kind != "orders":
        raise HTTPException(404, "No such plan to confirm.")
    token, _ = services.policy.signer.mint(proposal.id, proposal.content_hash, services.clock())
    result = await take_turn(
        services,
        request.app.state.model,
        request.app.state.model_settings,
        session_id,
        action={
            "tool": "place_order",
            "args": {"proposal_id": proposal.id, "confirmation_token": token},
        },
    )
    return _turn_out(result, services, session_id)


@router.get("/sessions/{session_id}/audit")
def audit(session_id: str, services: ServicesDep) -> schemas.AuditView:
    """Return the session's audit events and verify the chain."""
    with services.store.tx() as con:
        row = sessions.get(con, session_id)
    if row is None:
        raise HTTPException(404, "No such session.")
    path = services.log_path(session_id)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    check = verify_lines(lines, expected_head=row.audit_head)
    return schemas.AuditView(
        events=[json.loads(x) for x in lines if x.strip()],
        check=schemas.AuditCheck(
            ok=check.ok,
            events=check.events,
            head=check.head,
            anchored_head=row.audit_head,
            first_bad_seq=check.first_bad_seq,
            reason=check.reason,
        ),
    )
