"""Summarise the evidence into evidence/metrics.md (the Results slide).

    python scripts/run_personas.py && python scripts/run_redteam.py
    python scripts/metrics.py            # also runs the test suite for counts and coverage
    python scripts/metrics.py --no-tests

Numbers come only from the logs and reports, never typed by hand.
"""

import argparse
import json
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.audit.verify import verify_lines

SERVER_DIR = Path(__file__).resolve().parents[1]


def _events(path: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def _tests(out: Path) -> tuple[int, float]:
    """Run pytest; return (tests passed, line coverage %)."""
    cov = out / "run" / "coverage.json"
    proc = subprocess.run(  # noqa: S603 (fixed command)
        # Replace the project's addopts (which include -q) so the summary line is printed.
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "-o",
            "addopts=",
            "--cov=app",
            f"--cov-report=json:{cov}",
            "-m",
            "not llm",
        ],
        cwd=SERVER_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    tail = [line for line in proc.stdout.splitlines() if " passed" in line]
    passed = int(tail[-1].split(" passed")[0].split()[-1]) if tail else 0
    pct = json.loads(cov.read_text())["totals"]["percent_covered"] if cov.exists() else 0.0
    return passed, pct


def _checked_fills(events: dict[str, list[dict[str, Any]]]) -> int:
    """Count fills whose place_order call the guardian allowed first."""
    count = 0
    for evs in events.values():
        last_policy: dict[str, Any] | None = None
        for e in evs:
            if e["type"] == "policy" and e["payload"]["tool"] == "place_order":
                last_policy = e["payload"]
            if e["type"] == "fill" and last_policy is not None and last_policy["allowed"]:
                count += 1
    return count


def _shown(path: Path) -> str:
    """Return path relative to server/ when it is inside it."""
    full = path.resolve()
    return str(full.relative_to(SERVER_DIR)) if full.is_relative_to(SERVER_DIR) else str(full)


def main() -> int:
    """Write evidence/metrics.md and metrics.json."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=SERVER_DIR / "evidence")
    parser.add_argument("--no-tests", action="store_true")
    args = parser.parse_args()
    logs = sorted((args.out / "logs").glob("*.jsonl"))
    events = {p.stem: _events(p) for p in logs}
    chains = {p.stem: verify_lines(p.read_text(encoding="utf-8").splitlines()).ok for p in logs}
    all_events = [e for evs in events.values() for e in evs]
    denied = [
        e["payload"] for e in all_events if e["type"] == "policy" and not e["payload"]["allowed"]
    ]
    tool_refusals = [
        e["payload"]["error"]
        for e in all_events
        if e["type"] == "tool_result"
        and e["payload"]["error"]
        and e["payload"]["error"].get("rule_id")
    ]
    rules_fired = sorted({d["rule_id"] for d in denied} | {r["rule_id"] for r in tool_refusals})
    fills = [e for e in all_events if e["type"] == "fill"]
    replies = [e for e in all_events if e["type"] == "reply"]
    llm_replies = [e["payload"] for e in replies if e["payload"].get("tokens")]
    # A typed message goes to the LLM; a button press never does.
    typed_ms = [e["payload"]["latency_ms"] for e in replies if e["actor"] == "llm"]
    button_ms = [e["payload"]["latency_ms"] for e in replies if e["actor"] != "llm"]
    redteam = (
        json.loads((args.out / "redteam.json").read_text())
        if (args.out / "redteam.json").exists()
        else None
    )
    tasks = (
        json.loads((args.out / "tasks.json").read_text())
        if (args.out / "tasks.json").exists()
        else None
    )
    personas = (
        json.loads((args.out / "personas.json").read_text())
        if (args.out / "personas.json").exists()
        else None
    )
    tests, coverage = (0, 0.0) if args.no_tests else _tests(args.out)
    # Typed messages from the task and red-team runs: a larger sample than the personas.
    suite_ms = [
        r["latency_ms"]
        for report in (tasks, redteam)
        if report
        for r in report["results"]
        if r.get("latency_ms") is not None
        and r["passed"] is not None
        and "action" not in r.get("attack", "")
    ]

    data = {
        "llm": personas["llm"] if personas else "unknown",
        "redteam_passed": redteam["passed"] if redteam else None,
        "redteam_total": redteam["total"] if redteam else None,
        "redteam_llm": redteam["llm"] if redteam else None,
        "tasks_passed": tasks["passed"] if tasks else None,
        "tasks_total": tasks["total"] if tasks else None,
        "tasks_llm": tasks["llm"] if tasks else None,
        "audit_logs": len(logs),
        "audit_events": len(all_events),
        "chains_verified": sum(chains.values()),
        "guardian_refusals": len(denied) + len(tool_refusals),
        "rules_fired": rules_fired,
        "orders_filled": sum(len(f["payload"]["fills"]) for f in fills),
        "fills_after_allowed_check": _checked_fills(events),
        "median_button_reply_ms": statistics.median(button_ms) if button_ms else None,
        "median_typed_reply_ms": statistics.median(typed_ms) if typed_ms else None,
        "typed_replies": len(typed_ms),
        "median_suite_reply_ms": statistics.median(suite_ms) if suite_ms else None,
        "p90_suite_reply_ms": statistics.quantiles(suite_ms, n=10)[-1]
        if len(suite_ms) > 1
        else None,
        "suite_replies": len(suite_ms),
        "llm_turns": len(llm_replies),
        "tokens_per_llm_turn": round(statistics.mean(r["tokens"] for r in llm_replies))
        if llm_replies
        else None,
        "tests_passed": tests,
        "coverage_pct": round(coverage, 1),
    }
    (args.out / "metrics.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    rt = (
        f"{data['redteam_passed']} of {data['redteam_total']} ({data['redteam_llm']})"
        if redteam
        else "not run"
    )
    tk = (
        f"{data['tasks_passed']} of {data['tasks_total']} ({data['tasks_llm']})"
        if tasks
        else "not run"
    )
    lines = [
        "# Results",
        "",
        f"Generated by `scripts/metrics.py` from `{_shown(args.out)}/`. "
        f"Persona LLM: `{data['llm']}`.",
        "",
        "| Measure | Result |",
        "|---|---|",
        f"| Tasks completed from a typed request | {tk} |",
        f"| Red-team attacks handled safely | {rt} |",
        f"| Persona audit logs with a verified hash chain | {data['chains_verified']} of {data['audit_logs']} ({data['audit_events']} events) |",
        f"| Guardian refusals in the persona runs | {data['guardian_refusals']} ({', '.join(data['rules_fired'])}) |",
        f"| Sandbox orders filled after a user's Confirm | {data['orders_filled']} |",
        f"| Order placements made only after an allowed guardian check (CONF-01, LIM-01, SUIT-01) | {data['fills_after_allowed_check']} of {len(fills)} |",
        f"| Median reply time: button / typed message | {data['median_button_reply_ms']} ms / "
        f"{data['median_typed_reply_ms']} ms ({data['typed_replies']} typed) |",
        *(
            [
                f"| Typed-message reply time in the task and red-team runs, median / 90th "
                f"percentile | {data['median_suite_reply_ms']:.0f} ms / "
                f"{data['p90_suite_reply_ms']:.0f} ms ({data['suite_replies']} turns) |"
            ]
            if suite_ms
            else []
        ),
        f"| LLM turns / tokens per LLM turn | {data['llm_turns']} / {data['tokens_per_llm_turn']} |",
        f"| Automated tests passing / line coverage | {data['tests_passed']} / {data['coverage_pct']}% |",
    ]
    if data["llm"] == "fake":
        lines += [
            "",
            "Reply times and tokens with the fake LLM measure the system, not a model; rerun the "
            "persona and red-team scripts with `--llm` for model numbers.",
        ]
    (args.out / "metrics.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
