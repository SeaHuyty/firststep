"""Check that the model in server/.env works with Sprout, one feature at a time.

    python scripts/check_model.py

Sends three tiny requests through the same code path as the app: plain
text, text with system instructions, and a tool call. The first one that
fails names the feature the provider or model does not accept; the
seconds each took show whether a Sprout turn (several such requests)
fits LLM_TURN_TIMEOUT_S.
"""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic_ai import Agent

from app.core.settings import Settings
from app.llm.adapter import build_model, model_settings


def add(a: int, b: int) -> int:
    """Add two whole numbers."""
    return a + b


async def main() -> int:
    """Run the three checks and report each."""
    settings = Settings()
    model, provider = build_model(settings)
    print(f"provider: {provider}")
    if provider == "fake":
        print("LLM_PROVIDER is fake or the key is missing: nothing to check.")
        return 1
    ms = model_settings(settings)
    checks = [
        ("plain text", Agent(model, model_settings=ms), "Reply with the word ok."),
        (
            "system instructions",
            Agent(model, model_settings=ms, instructions="You are terse. Reply with one word."),
            "Say ok.",
        ),
        (
            "tool call",
            Agent(model, model_settings=ms, tools=[add], instructions="Use the add tool."),
            "What is 2 + 3? Use the tool.",
        ),
    ]
    failed = 0
    for name, agent, prompt in checks:
        started = time.perf_counter()
        try:
            result = await asyncio.wait_for(agent.run(prompt), 60)
            took = time.perf_counter() - started
            print(f"ok    {name} ({took:.1f}s): {result.output.strip()[:60]!r}")
        except Exception as e:  # report every failure plainly
            failed += 1
            print(f"FAIL  {name}: {type(e).__name__}: {str(e)[:300]}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
