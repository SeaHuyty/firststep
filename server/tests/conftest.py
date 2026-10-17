from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic_ai import models

from app.api.app import create_app
from app.core.settings import Settings

models.ALLOW_MODEL_REQUESTS = False  # never call a real LLM from tests

FIXED_NOW = datetime(2026, 10, 17, 10, 0, tzinfo=UTC)


def test_settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        llm_provider="fake",
        confirm_secret="test-secret-at-least-16-bytes",
        db_path=tmp_path / "sandbox.db",
        evidence_dir=tmp_path / "evidence",
    )


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    app = create_app(test_settings(tmp_path), clock=lambda: FIXED_NOW)
    with TestClient(app) as c:
        yield c


class Session:
    """Drives one session through the API like the UI does."""

    def __init__(self, client: TestClient, persona: str | None = None) -> None:
        self.client = client
        r = client.post("/api/sessions", json={"persona": persona})
        assert r.status_code == 200, r.text
        self.view = r.json()
        self.id = self.view["id"]
        self.last: dict[str, Any] = {}

    def act(self, tool: str, **args: Any) -> dict[str, Any]:
        r = self.client.post(
            f"/api/sessions/{self.id}/turn", json={"action": {"tool": tool, "args": args}}
        )
        assert r.status_code == 200, r.text
        self.last = r.json()
        return self.last

    def say(self, text: str) -> dict[str, Any]:
        r = self.client.post(f"/api/sessions/{self.id}/turn", json={"text": text})
        assert r.status_code == 200, r.text
        self.last = r.json()
        return self.last

    def answer(self, question_id: str, value: Any) -> dict[str, Any]:
        return self.act("answer_question", question_id=question_id, value=value)

    def confirm(self, proposal_id: str) -> dict[str, Any]:
        r = self.client.post(f"/api/sessions/{self.id}/confirm/{proposal_id}")
        assert r.status_code == 200, r.text
        self.last = r.json()
        return self.last

    def cards(self, kind: str) -> list[dict[str, Any]]:
        return [c for c in self.last["cards"] if c["type"] == kind]

    def audit(self) -> dict[str, Any]:
        r = self.client.get(f"/api/sessions/{self.id}/audit")
        assert r.status_code == 200
        return r.json()


def answer_all(s: Session, answers: dict[str, Any]) -> None:
    """Answer every question the session asks, in the order it asks."""
    for _ in range(20):
        questions = [
            c
            for c in s.last.get("cards", s.view["messages"][-1]["cards"])
            if c["type"] == "question"
        ]
        if not questions or questions[0]["question_id"] not in answers:
            return
        qid = questions[0]["question_id"]
        s.answer(qid, answers[qid])
