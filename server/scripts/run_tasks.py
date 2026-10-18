"""Run the task-completion suite and write evidence/tasks.md and tasks.json.

    python scripts/run_tasks.py          # scripted fake LLM (most tasks need a real model)
    python scripts/run_tasks.py --llm    # the provider in server/.env

Each task starts a fresh session in a known state, sends one message the
way a person would type it, and is judged from the audit events of that
turn: the tools the LLM called and their arguments, and the guardian's
decisions. The red team (run_redteam.py) checks what Sprout refuses;
this checks what it gets done.
"""

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import LEO, Session, make_client, write_json
from run_redteam import _refusals
from run_redteam import setup as redteam_setup

SERVER_DIR = Path(__file__).resolve().parents[1]
AREAS = {
    "profiling": "Risk profiling and money check",
    "planning": "Goals and planning",
    "comparison": "Product comparison",
    "dialogue": "Advisory dialogue",
    "execution": "Acting on the plan",
    "monitoring": "Watching the plan",
}


def setup(client: Any, state: str) -> Session:
    """Return a session driven to a named state."""
    if state == "after_age":
        s = Session(client, "leo")
        s.act("answer_question", question_id="age", value=LEO["age"])
        return s
    if state == "at_debts":
        s = Session(client, "leo")
        s.answer_all(
            {k: LEO[k] for k in ("age", "monthly_income", "monthly_expenses", "liquid_savings")}
        )
        return s
    if state == "invested":
        s = redteam_setup(client, "proposed")
        s.act("prepare_orders")
        s.confirm()
        return s
    return redteam_setup(client, state)


def matches(expected: Any, actual: Any) -> bool:
    """Return whether actual contains expected (dict subset; list: each item present)."""
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            k in actual and matches(v, actual[k]) for k, v in expected.items()
        )
    if isinstance(expected, list):
        return isinstance(actual, list) and all(
            any(matches(e, a) for a in actual) for e in expected
        )
    if isinstance(expected, int | float) and isinstance(actual, int | float):
        return abs(float(expected) - float(actual)) < 0.01
    return bool(expected == actual)


def judge(
    task: dict[str, Any], events: list[dict[str, Any]], reply: str
) -> tuple[bool, list[str]]:
    """Return (passed, observations) for one task."""
    calls = [e["payload"] for e in events if e["type"] == "tool_call" and e["actor"] == "llm"]
    refused = _refusals(events)
    notes = [f"called {', '.join(c['tool'] for c in calls)}"] if calls else ["no tool called"]
    if refused:
        notes.append(f"refused: {', '.join(sorted(refused))}")
    ok = True
    for want in task["expect"]:
        if "call" in want:
            tools = want["call"] if isinstance(want["call"], list) else [want["call"]]
            options = want.get("args_any") or [want.get("args", {})]
            hit = any(
                c["tool"] in tools and any(matches(o, c.get("args", {})) for o in options)
                for c in calls
            )
            ok &= hit
            if not hit:
                notes.append(
                    f"missing {'/'.join(tools)}"
                    + (" with the right details" if any(options) else "")
                )
        if "forbid" in want:
            bad = [c["tool"] for c in calls if c["tool"] in want["forbid"]]
            ok &= not bad
            if bad:
                notes.append(f"should not call {', '.join(bad)}")
        if "refused" in want:
            ok &= want["refused"] in refused
        if "reply_has" in want:
            missing = [w for w in want["reply_has"] if w.lower() not in reply.lower()]
            ok &= not missing
            if missing:
                notes.append(f"reply lacks {', '.join(missing)}")
    if any(e["type"] == "fill" for e in events):
        ok = False
        notes.append("an order filled")
    return ok, notes


def main() -> int:
    """Run every task, write the report, and return 0 (a score, not a gate)."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--llm", action="store_true", help="use the real provider from .env")
    parser.add_argument("--out", type=Path, default=SERVER_DIR / "evidence")
    args = parser.parse_args()
    tasks = yaml.safe_load((SERVER_DIR / "scripts" / "tasks.yaml").read_text())["tasks"]
    results = []
    with make_client(args.out / "run" / "tasks", real_llm=args.llm) as client:
        policy = client.app.state.services.policy  # type: ignore[attr-defined]
        provider = client.app.state.llm_provider  # type: ignore[attr-defined]
        for task in tasks:
            s = setup(client, task["state"])
            before = len(s.audit()["events"])
            s.say(task["prompt"])
            audit = s.audit()
            ok, notes = judge(task, audit["events"][before:], s.last["reply"])
            lang = policy.language(s.last["reply"])
            if lang:
                ok = False
                notes.append(f"LANG hits: {', '.join(lang)}")
            ok &= audit["check"]["ok"]
            results.append(
                {
                    "id": task["id"],
                    "area": task["area"],
                    "prompt": task["prompt"],
                    "passed": ok,
                    "notes": notes,
                    "reply": s.last["reply"],
                }
            )
            print(f"{task['id']} {'pass' if ok else 'FAIL'}: {'; '.join(notes)}")
    passed = sum(r["passed"] for r in results)
    by_area: dict[str, Counter[str]] = {}
    for r in results:
        by_area.setdefault(r["area"], Counter())["passed" if r["passed"] else "failed"] += 1
    write_json(
        args.out / "tasks.json",
        {"llm": provider, "passed": passed, "total": len(results), "results": results},
    )
    lines = [
        "# Task-completion results",
        "",
        f"LLM: `{provider}`. Completed **{passed} of {len(results)}** tasks. Each task is one "
        "message typed the way a first-time investor would, judged from the audit log: the tools "
        "the model called, their arguments and the guardian's decisions. Every task also "
        "requires that nothing filled, the reply passed LANG-* and the hash chain verified.",
        "",
        "| Area | Completed |",
        "|---|---|",
    ]
    for area, c in by_area.items():
        lines.append(f"| {AREAS.get(area, area)} | {c['passed']} of {c['passed'] + c['failed']} |")
    lines += ["", "| ID | Area | Typed message | Result | Observed |", "|---|---|---|---|---|"]
    for r in results:
        prompt = r["prompt"].replace("|", "\\|")
        lines.append(
            f"| {r['id']} | {AREAS.get(r['area'], r['area'])} | {prompt} | "
            f"{'done' if r['passed'] else '**missed**'} | {'; '.join(r['notes'])} |"
        )
    (args.out / "tasks.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"tasks ({provider}): {passed}/{len(results)} completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
