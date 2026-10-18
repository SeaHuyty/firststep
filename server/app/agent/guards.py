"""Input guard and output filter around the LLM (OWASP LLM01).

The input guard masks personal data before anything is logged or sent
to a model, and flags common injection phrasings so the turn is logged
and the model is reminded of its rules. It does not try to block every
injection: the real defence is that the model cannot execute anything
the guardian has not allowed. The output filter checks Sprout's reply
against the LANG-* rules before it is shown.
"""

import re
from dataclasses import dataclass

from app.policy.engine import Policy

INJECTION_PATTERNS = (
    r"ignore (all |any |your |the )?(previous |prior |above )?(instructions|rules)",
    r"disregard (your|the) (rules|instructions)",
    r"you are now",
    r"pretend (to be|you are)",
    r"act as (an?|my) ",
    r"\bsystem prompt\b",
    r"^\s*system\s*:",
    r"developer mode",
    r"jailbreak",
    r"skip (the |your )?(questions|questionnaire|checks|rules)",
    r"i('m| am) a (professional|qualified|accredited) investor",
    r"(confirmation|confirm) token",
)
_INJECTION = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE | re.MULTILINE)

_PII = (
    ("[card number]", re.compile(r"\b(?:\d[ -]?){13,19}\b")),
    ("[email]", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    ("[id number]", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("[phone]", re.compile(r"\+\d[\d ()-]{7,}\d")),
)

DISCLOSURE = "This is an educational simulation, not financial advice."
# Shown when a reply and its one rewrite both break LANG-*. Usually the
# client asked for a promise or a forecast, so it answers that honestly.
SAFE_FALLBACK = (
    "No one can promise what markets will do, or say which fund comes out ahead. Your plan "
    "shows a range of outcomes from replaying past markets, not a forecast. Ask me about any "
    "part of it."
)


@dataclass(frozen=True, slots=True)
class InputCheck:
    """The cleaned text and what the guard noticed."""

    text: str
    injection: bool
    masked: tuple[str, ...]


def check_input(text: str) -> InputCheck:
    """Return the text with PII masked and injection flagged."""
    masked = []
    for label, pattern in _PII:
        if pattern.search(text):
            masked.append(label)
            text = pattern.sub(label, text)
    return InputCheck(text=text, injection=bool(_INJECTION.search(text)), masked=tuple(masked))


def check_output(policy: Policy, reply: str) -> list[str]:
    """Return the LANG-* rules the reply breaks (empty when clean)."""
    return policy.language(reply)


def with_disclosure(reply: str) -> str:
    """Return the reply ending with the disclosure, added once."""
    return reply if DISCLOSURE.lower() in reply.lower() else f"{reply.rstrip()} {DISCLOSURE}"
