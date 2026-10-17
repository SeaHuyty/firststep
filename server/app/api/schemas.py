"""Request and response bodies.

FastAPI's OpenAPI schema built from these is the contract the frontend
generates its types from.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.tools.cards import Card


class Body(BaseModel):
    """Base for request bodies: unknown keys are rejected."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class NewSession(Body):
    """Start a session, optionally as a demo person."""

    persona: str | None = Field(default=None, pattern=r"^(amina|leo|mei)$")


class Action(Body):
    """A chip or button: the tool to run and its arguments."""

    tool: str = Field(max_length=40)
    args: dict[str, Any] = Field(default_factory=dict)
    # The words on the chip or button, kept as the person's message so
    # the chat reads the same after a reload. Checked like typed text.
    label: str | None = Field(default=None, min_length=1, max_length=80)


class TurnIn(Body):
    """Either typed text or a chip/button action."""

    text: str | None = Field(default=None, min_length=1, max_length=1000)
    action: Action | None = None

    @model_validator(mode="after")
    def _one_of(self) -> "TurnIn":
        if (self.text is None) == (self.action is None):
            raise ValueError("send either text or action")
        return self


class Message(BaseModel):
    """One chat message with its cards."""

    role: str
    text: str
    cards: list[Card]


class PersonaHint(BaseModel):
    """What a demo person answers, so a demo can be tapped through."""

    name: str
    tagline: str
    answers: dict[str, Any]
    goal: dict[str, Any] | None
    opening_line: str


class SessionView(BaseModel):
    """Everything needed to (re)draw a session after a refresh."""

    id: str
    persona: PersonaHint | None
    stage: str
    sim_month: str
    messages: list[Message]


class TurnOut(BaseModel):
    """What changed in one turn."""

    reply: str
    cards: list[Card]
    stage: str
    sim_month: str
    steps: list[str]
    pending_confirmation: str | None


class AuditCheck(BaseModel):
    """Result of verifying the session's chain against its anchor."""

    ok: bool
    events: int
    head: str
    anchored_head: str
    first_bad_seq: int | None
    reason: str | None


class AuditView(BaseModel):
    """The session's audit events and the chain check."""

    events: list[dict[str, Any]]
    check: AuditCheck


class Health(BaseModel):
    """Liveness and which LLM provider is in use."""

    ok: bool
    llm: str
