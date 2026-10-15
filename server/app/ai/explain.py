from collections.abc import AsyncIterator

from pydantic_ai import Agent

from app.ai.models import pick_model
from app.config import Settings
from app.domain.catalog import BUCKET_META, LABELS
from app.domain.plan import analyse
from app.domain.schemas import BUCKETS, Pct, Profile
from app.domain.sources import BY_BUCKET, sources_for

SYSTEM = """You are the explanation layer of an AI wealth advisor prototype.
The allocation was already decided by deterministic code. Never change, question or recalculate it; only explain it.
Write one short paragraph (2 sentences max) per allocation bucket, in the order given, each starting with the bucket name in bold-free plain text followed by a colon.
Ground every factual claim in the provided SOURCES and cite with the marker [S#] right after the claim. Use one marker per source, like [S1][S3], never combined like [S1, S3]. Cite only source ids that appear in SOURCES. Do not invent facts, figures, returns or URLs.
Tie each explanation to the client's profile (goal, horizon, risk, emergency savings, debt).
Plain language, no markdown, no guarantees of returns. Finish with one sentence saying this is educational, not personalised financial advice."""


def usd(n: float) -> str:
    return f"${round(n):,}"


def _slices(profile: Profile, pct: Pct) -> list[tuple[str, int, int]]:
    """(bucket, pct, dollars) for non-zero buckets."""
    return [(b, pct[b], int(profile.amount * pct[b] / 100 + 0.5)) for b in BUCKETS if pct[b] > 0]


def fallback_text(profile: Profile, pct: Pct) -> str:
    body = "\n\n".join(
        f"{BUCKET_META[b]['label']}: {usd(amount)} ({p}%). {BUCKET_META[b]['why']} {''.join(f'[{i}]' for i in BY_BUCKET[b])}"
        for b, p, amount in _slices(profile, pct)
    )
    return (
        f"{body}\n\n(Demo explanation: no AI key configured. Add GOOGLE_GENERATIVE_AI_API_KEY or "
        "ANTHROPIC_API_KEY to server/.env for a personalised one.) This is educational, not personalised financial advice."
    )


def build_prompt(profile: Profile, pct: Pct, adjusted: bool) -> str:
    slices = _slices(profile, pct)
    note = ", adjusted by the client within safe limits from the rules-based default" if adjusted else ""
    allocation = "\n".join(f"- {BUCKET_META[b]['label']}: {usd(amount)} ({p}%)" for b, p, amount in slices)
    sources = "\n".join(f'[{s.id}] {s.publisher}, "{s.title}": {s.summary}' for s in sources_for([b for b, _, _ in slices]))
    return f"""CLIENT PROFILE
- Available money: {usd(profile.amount)}
- Goal: {LABELS['goal'][profile.goal]}
- Time horizon: {LABELS['horizon'][str(profile.horizon)]}
- Risk tolerance: {LABELS['risk'][str(profile.risk)]}
- Emergency savings: {LABELS['emergency'][profile.emergency]}
- Debt: {LABELS['debt'][profile.debt]}
- Financial health score: {analyse(profile)['score']}/100

ALLOCATION (fixed{note})
{allocation}

SOURCES
{sources}"""


async def stream_explanation(settings: Settings, profile: Profile, pct: Pct, adjusted: bool) -> AsyncIterator[str]:
    model = pick_model(settings, "explain")
    if model is None:
        yield fallback_text(profile, pct)
        return

    agent = Agent(model, instructions=SYSTEM)
    async with agent.run_stream(build_prompt(profile, pct, adjusted)) as result:
        async for chunk in result.stream_text(delta=True):
            yield chunk
