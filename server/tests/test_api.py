import pytest
from fastapi.testclient import TestClient
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import FunctionModel

from app.config import Settings, get_settings
from app.domain.catalog import PRODUCTS
from app.main import app

PROFILE = {"amount": 10000, "goal": "wealth", "horizon": 7, "emergency": "insufficient", "risk": 2, "debt": "none"}
DEFAULT_PCT = {"emergency": 20, "stocks": 40, "bonds": 23, "cash": 12, "alt": 5}
ALL_CONFIRMED = ["amount", "goal", "horizon", "emergency", "risk", "debt"]


@pytest.fixture
def client():
    # No AI key and no live market (never touch the network in tests), regardless of server/.env.
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, google_generative_ai_api_key=None, anthropic_api_key=None, market_enabled=False)
    yield TestClient(app)
    app.dependency_overrides.clear()


def chat_body(text: str, **over):
    return {"messages": [{"role": "user", "content": text}], "profile": PROFILE, "confirmed": ALL_CONFIRMED, "pct": DEFAULT_PCT, "picks": [], **over}


def test_catalog(client):
    d = client.get("/api/catalog").json()
    assert set(d) == {"labels", "buckets", "group_buckets", "products", "sources", "stock_universe", "satellite"}
    assert d["stock_universe"]["NVDA"]["sector"] == "Information Technology" and len(d["stock_universe"]) > 400
    assert d["labels"]["horizon"]["3"] == "2–5 years"
    assert d["sources"]["S1"]["url"].startswith("https://www.investor.gov")


def test_plan(client):
    d = client.post("/api/plan", json={"profile": PROFILE}).json()
    assert d["base"] == DEFAULT_PCT
    assert d["limits"]["max"]["stocks"] == 55
    assert d["analysis"]["score"] == 85
    assert {"VT", "VOO", "BND", "HYSA", "VNQ"} == set(d["picks"])  # moderate, with an alternatives slice


def test_suggested_picks_follow_the_risk_level(client):
    def stock_risk(risk):
        picks = client.post("/api/plan", json={"profile": {**PROFILE, "risk": risk}}).json()["picks"]
        stocks = [p for p in PRODUCTS["Global Stocks (ETF)"] if p.ticker in picks and p.ticker != "VNQ"]
        return sum(p.risk for p in stocks) / len(stocks)

    assert stock_risk(1) < stock_risk(3)
    assert "QQQM" in client.post("/api/plan", json={"profile": {**PROFILE, "risk": 3}}).json()["picks"]
    assert "QQQM" not in client.post("/api/plan", json={"profile": {**PROFILE, "risk": 1}}).json()["picks"]


def test_invalid_profile_is_rejected_without_echoing_input(client):
    r = client.post("/api/plan", json={"profile": {**PROFILE, "amount": -5}})
    assert r.status_code == 422 and r.json() == {"error": "Invalid request"}


def test_validate_allocation(client):
    ok = client.post("/api/allocation/validate", json={"profile": PROFILE, "pct": DEFAULT_PCT}).json()
    bad = client.post("/api/allocation/validate", json={"profile": PROFILE, "pct": {**DEFAULT_PCT, "stocks": 90, "bonds": 0, "cash": 0}}).json()
    assert ok == {"valid": True} and bad == {"valid": False}


def test_whatif_without_live_data_uses_standard_assumptions(client):
    body = {"profile": PROFILE, "monthly": 100, "years": 10, "risk": 2, "basis": "history"}
    d = client.post("/api/whatif", json=body).json()  # fixture disables the market => assumptions
    assert d["basis"] == "assumed" and d["stats"] is None
    assert [s[-1] for s in d["series"]] == [22000, 31998, 40491]
    assert client.post("/api/whatif", json={**body, "years": 999}).status_code == 422


def test_explain_falls_back_without_key(client):
    text = client.post("/api/explain", json={"profile": PROFILE}).text
    assert "Demo explanation" in text and "[S5]" in text and "$2,000" in text


def test_explain_ignores_an_allocation_that_breaks_the_guardrails(client):
    bad = {"emergency": 0, "stocks": 100, "bonds": 0, "cash": 0, "alt": 0}
    text = client.post("/api/explain", json={"profile": PROFILE, "pct": bad}).text
    assert "$2,000" in text and "$10,000 (100%)" not in text  # served the default plan instead


def test_chat_needs_a_key(client):
    assert client.post("/api/chat", json=chat_body("hi")).status_code == 503


def test_chat_last_message_must_be_from_user(client):
    body = chat_body("hi", messages=[{"role": "assistant", "content": "hello"}])
    assert client.post("/api/chat", json=body).status_code == 422


def scripted(monkeypatch, tool_calls: list[tuple[str, dict]], reply: str = "Proposed."):
    """Replace the real LLM with one that makes the given tool calls, then replies."""

    def fake(messages, info):
        if any(isinstance(p, ToolReturnPart) for m in messages for p in m.parts):
            return ModelResponse(parts=[TextPart(reply)])
        return ModelResponse(parts=[ToolCallPart(name, args) for name, args in tool_calls])

    monkeypatch.setattr("app.ai.advisor.pick_model", lambda settings, kind: FunctionModel(fake))


def test_advisor_proposal_is_clamped_by_guardrails(client, monkeypatch):
    # The "AI" asks for 95% stocks; code must cap it at the profile's limit (55%) and rebalance to 100.
    scripted(monkeypatch, [("propose_allocation", {"targets": {"stocks": 95}, "reason": "max growth"})])
    d = client.post("/api/chat", json=chat_body("put 95% in stocks")).json()
    alloc = next(a for a in d["actions"] if a["type"] == "allocation")
    assert alloc["after"]["stocks"] == 55 and sum(alloc["after"].values()) == 100
    assert alloc["before"] == DEFAULT_PCT and alloc["notes"]
    assert d["reply"] == "Proposed."


def test_advisor_rejects_products_outside_the_catalog(client, monkeypatch):
    scripted(monkeypatch, [("propose_products", {"group": "Global Stocks (ETF)", "tickers": ["DOGE"], "reason": "hot"})])
    d = client.post("/api/chat", json=chat_body("buy dogecoin")).json()
    assert not [a for a in d["actions"] if a["type"] == "products"]


def test_advisor_accepts_catalog_products_and_profile_updates(client, monkeypatch):
    scripted(
        monkeypatch,
        [
            ("update_profile", {"risk": "aggressive", "amount": 15000}),
            ("propose_products", {"group": "Global Stocks (ETF)", "tickers": ["VT", "VTI"], "reason": "cheap and broad"}),
            ("show_step", {"step": "products"}),
        ],
    )
    d = client.post("/api/chat", json=chat_body("I got a bonus and feel braver")).json()
    kinds = {a["type"]: a for a in d["actions"]}
    assert kinds["profile"]["updates"] == {"amount": 15000, "risk": 3}
    assert kinds["products"]["tickers"] == ["VT", "VTI"]
    assert kinds["goto"]["step"] == 2  # products live on the combined plan page


def failing(status: int):
    """A fake LLM whose provider always answers with an HTTP error (e.g. 429 quota exceeded)."""
    from pydantic_ai.exceptions import ModelHTTPError

    def call(messages, info):
        raise ModelHTTPError(status, "fake-model")

    async def stream(messages, info):
        raise ModelHTTPError(status, "fake-model")
        yield ""  # pragma: no cover  (makes this an async generator)

    return FunctionModel(call, stream_function=stream)


@pytest.mark.parametrize("status,expected", [(429, 429), (500, 502)])
def test_provider_errors_become_clean_http_errors(client, monkeypatch, status, expected):
    monkeypatch.setattr("app.ai.explain.pick_model", lambda settings, kind: failing(status))
    monkeypatch.setattr("app.ai.advisor.pick_model", lambda settings, kind: failing(status))
    for r in (client.post("/api/explain", json={"profile": PROFILE}), client.post("/api/chat", json=chat_body("hi"))):
        assert r.status_code == expected
        assert "fake-model" not in r.text  # provider details are not leaked
