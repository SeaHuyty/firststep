"""Drives the API in-process for the evidence scripts.

Uses FastAPI's TestClient against the real app, so evidence runs go
through exactly the same routes, guardian and audit log as the UI.
"""

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app.api.app import create_app
from app.core.settings import Settings

LEO = {
    "age": 27,
    "monthly_income": 3800,
    "monthly_expenses": 2300,
    "liquid_savings": 15000,
    "debts": [{"kind": "student_loan", "balance_usd": 12000, "apr_pct": 5.5}],
    "income_stability": "stable",
    "dependants": 0,
    "loss_capacity": 4,
    "drop_reaction": 3,
    "priority": 3,
    "range_choice": 3,
    "self_view": 3,
    "bad_year": 3,
}
LEO_GOAL = {
    "name": "Long-term growth",
    "target_usd": 60000,
    "horizon_years": 10,
    "lump_sum_usd": 6000,
    "monthly_usd": 300,
}
AMINA = {
    "age": 21,
    "monthly_income": 1400,
    "monthly_expenses": 1150,
    "liquid_savings": 600,
    "debts": [{"kind": "credit_card", "balance_usd": 1750, "apr_pct": 22.9}],
}
MEI = {
    **LEO,
    "age": 58,
    "monthly_income": 5200,
    "monthly_expenses": 3400,
    "liquid_savings": 40000,
    "debts": [],
    "loss_capacity": 2,
    "drop_reaction": 2,
    "priority": 2,
    "range_choice": 2,
    "self_view": 2,
    "bad_year": 2,
}
MEI_GOAL = {
    "name": "Retirement top-up",
    "target_usd": 45000,
    "horizon_years": 5,
    "lump_sum_usd": 20000,
    "monthly_usd": 500,
}


class Session:
    """One session driven like the UI drives it."""

    def __init__(self, client: TestClient, persona: str | None = None) -> None:
        """Start a session, optionally as a demo person."""
        self.client = client
        r = client.post("/api/sessions", json={"persona": persona})
        r.raise_for_status()
        self.view = r.json()
        self.id: str = self.view["id"]
        self.last: dict[str, Any] = {"cards": self.view["messages"][-1]["cards"]}

    def _turn(self, body: dict[str, Any]) -> dict[str, Any]:
        r = self.client.post(f"/api/sessions/{self.id}/turn", json=body)
        r.raise_for_status()
        self.last = r.json()
        return self.last

    def act(self, tool: str, **args: Any) -> dict[str, Any]:
        """Run a chip or button action."""
        return self._turn({"action": {"tool": tool, "args": args}})

    def say(self, text: str) -> dict[str, Any]:
        """Send typed text to the LLM."""
        return self._turn({"text": text})

    def confirm(self) -> dict[str, Any]:
        """Press Confirm on the pending proposal."""
        pid = self.last["pending_confirmation"]
        r = self.client.post(f"/api/sessions/{self.id}/confirm/{pid}")
        r.raise_for_status()
        self.last = r.json()
        return self.last

    def answer_all(self, answers: dict[str, Any]) -> None:
        """Answer every question asked, in order, from a dict."""
        for _ in range(20):
            qs = [c for c in self.last["cards"] if c["type"] == "question"]
            if not qs or qs[0]["question_id"] not in answers:
                return
            qid = qs[0]["question_id"]
            self.act("answer_question", question_id=qid, value=answers[qid])

    def audit(self) -> dict[str, Any]:
        """Return the audit events and the chain check."""
        r = self.client.get(f"/api/sessions/{self.id}/audit")
        r.raise_for_status()
        data: dict[str, Any] = r.json()
        return data

    def cards(self, kind: str) -> list[dict[str, Any]]:
        """Return the last turn's cards of one type."""
        return [c for c in self.last["cards"] if c["type"] == kind]


# The replies a turn gives when the provider did not answer (quota,
# overload, timeout): such a turn is "no answer", neither pass nor fail.
NO_ANSWER = ("Sorry, Sprout couldn't reach", "Sorry, Sprout didn't answer")

# No browser waits on an evidence run, so a slow free model gets longer
# than the web app allows before a turn counts as unanswered.
EVIDENCE_TURN_TIMEOUT_S = 120.0


def make_client(evidence_dir: Path, *, real_llm: bool) -> TestClient:
    """Return a client for an app writing its logs under evidence_dir."""
    base = Settings() if real_llm else Settings(_env_file=None, llm_provider="fake")
    settings = base.model_copy(
        update={
            "evidence_dir": evidence_dir,
            "db_path": evidence_dir / "sandbox.db",
            "llm_turn_timeout_s": max(base.llm_turn_timeout_s, EVIDENCE_TURN_TIMEOUT_S),
        }
    )
    return TestClient(create_app(settings))


def write_json(path: Path, data: object) -> None:
    """Write pretty JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
