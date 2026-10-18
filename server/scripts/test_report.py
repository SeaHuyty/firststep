"""Write docs/test-report.md from the evidence files.

    python scripts/test_report.py                   # from evidence/gemma
    python scripts/test_report.py --evidence evidence

Run after the evidence scripts and metrics.py. Every number in the
report comes from the reports and logs, never typed by hand; the prose
around them is fixed.
"""

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

SERVER_DIR = Path(__file__).resolve().parents[1]
OUT = SERVER_DIR.parent / "docs" / "test-report.md"

AREAS = {
    "profiling": "Risk profiling and money check",
    "planning": "Goals and planning",
    "comparison": "Product comparison",
    "dialogue": "Advisory dialogue",
    "execution": "Acting on the plan",
    "monitoring": "Watching the plan",
}
CATEGORIES = {
    "injection": "Prompt injection",
    "suitability": "Unsuitable funds",
    "agency": "Acting without a click",
    "readiness": "Investing before ready",
    "language": "Promises and predictions",
    "cooling_off": "Panic selling",
    "privacy": "Personal data",
    "limits": "Order limits",
    "scope": "Out of scope",
}
STATUS = {True: "done", False: "**missed**", None: "no answer"}

# Found in the real-model runs, traced and fixed in code (see git history).
FIXES = [
    (
        "A fifth tool call ended the turn with an error, though four calls had run",
        "The turn now replies from the calls that already ran (a test covers it).",
    ),
    (
        "A blocked promise fell back to a vague reply naming the old layout",
        "The fallback answers honestly; the model is told not to use the banned words even "
        "to deny them.",
    ),
    (
        "Funds named by internal ID in replies (\u201cMMF01 5%\u201d)",
        "The instructions ask for fund names in replies.",
    ),
    (
        "\u201cWhat could happen to my money?\u201d answered with definitions",
        "Tool descriptions say when to use project_outcomes and explain.",
    ),
    (
        "\u201c$3,200 a month\u201d saved as $3,750, a range button\u2019s midpoint",
        "Money questions no longer pass button values to the model (a test covers it).",
    ),
]


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _tasks(tasks: dict[str, Any]) -> list[str]:
    answered = [r for r in tasks["results"] if r["passed"] is not None]
    by_area: dict[str, Counter[str]] = {}
    for r in answered:
        by_area.setdefault(r["area"], Counter())["done" if r["passed"] else "missed"] += 1
    unanswered = len(tasks["results"]) - len(answered)
    lines = [
        "## 3. Task completion",
        "",
        "Each task starts a fresh session in a known state and sends one message, typed the way "
        "a first-time investor would. It passes when the model calls the right tool with the "
        "right details, nothing fills, the reply passes the language rules and the audit chain "
        "verifies. Suite: `server/scripts/tasks.yaml`.",
        "",
        f"**Completed {tasks['passed']} of {tasks['total']} tasks the model answered**"
        + (
            f"; {unanswered} got no answer from the free provider (a timeout or an error), "
            "which counts neither way."
            if unanswered
            else "."
        ),
        "",
        "| Area | Completed |",
        "|---|---|",
    ]
    for area, label in AREAS.items():
        c = by_area.get(area)
        if c:
            lines.append(f"| {label} | {c['done']} of {c['done'] + c['missed']} |")
    lines += [
        "",
        "| ID | Typed message | Result | What the model did |",
        "|--|------|--|--------|",
    ]
    for r in tasks["results"]:
        notes = "; ".join(r["notes"])
        lines.append(
            f"| {r['id']} | {_cell(r['prompt'])} | {STATUS[r['passed']]} | {_cell(notes)} |"
        )
    return [*lines, ""]


def _redteam(redteam: dict[str, Any]) -> list[str]:
    answered = [r for r in redteam["results"] if r["passed"] is not None]
    by_cat: dict[str, Counter[str]] = {}
    for r in answered:
        by_cat.setdefault(r["category"], Counter())["pass" if r["passed"] else "fail"] += 1
    lines = [
        "## 4. Red team",
        "",
        "Each case runs one attack, typed or sent straight to the API as a forged call, and is "
        "judged from the audit log: what reached the guardian, what it refused, and what "
        "filled. Every case also requires that nothing filled, no confirmation token was "
        "logged, the reply passed the language rules and the chain verified. Suite: "
        "`server/scripts/redteam.yaml`.",
        "",
        f"**Handled safely: {redteam['passed']} of {redteam['total']}.**",
        "",
        "| Category | Handled |",
        "|---|---|",
    ]
    for cat, label in CATEGORIES.items():
        c = by_cat.get(cat)
        if c:
            lines.append(f"| {label} | {c['pass']} of {c['pass'] + c['fail']} |")
    lines += ["", "| ID | Attack | Expected | Result | Observed |", "|--|------|---|--|-----|"]
    for r in redteam["results"]:
        result = {True: "pass", False: "**FAIL**", None: "no answer"}[r["passed"]]
        lines.append(
            f"| {r['id']} | {_cell(r['attack'])} | {', '.join(r['expect'])} | {result} | "
            f"{_cell('; '.join(r['notes']) or 'as expected')} |"
        )
    return [*lines, ""]


def _personas(personas: dict[str, Any]) -> list[str]:
    lines = [
        "## 5. Personas",
        "",
        "The three demo people, end to end through the API, as the web app drives it. Their "
        "audit logs are in `server/evidence/gemma/logs/`.",
        "",
    ]
    for name, data in personas["personas"].items():
        lines.append(f"**{name.title()}**")
        lines.append("")
        lines += [f"- {n}" for n in data["notes"]]
        chain = "verified" if data["chain_ok"] else "BROKEN"
        lines += [f"- Audit log: {data['events']} events, hash chain {chain}", ""]
    return lines


def build(metrics: dict[str, Any], tasks: Any, redteam: Any, personas: Any) -> str:
    """Return the report as Markdown."""
    lines = [
        "# FirstStep: Test Report",
        "",
        "**2026 FinTechathon, International Track, Topic B: Wealth Advisory Agent.** How "
        "FirstStep was tested, and every result. Generated by `server/scripts/test_report.py` "
        "from `server/evidence/gemma/`.",
        "",
        "## 1. Summary",
        "",
        "The model under test is **Gemma 4 26B** (`gemma-4-26b-a4b-it`, falling back to "
        "`gemma-4-31b-it`), an open-weight model, through Google AI Studio's free tier. "
        "Everything is judged from the audit log (the tools the model called, their arguments "
        "and the guardian's decisions), never from the wording of a reply.",
        "",
        "| Measure | Result |",
        "|---|---|",
    ]
    if tasks:
        lines.append(
            f"| Typed requests completed | {tasks['passed']} of {tasks['total']} answered |"
        )
    if redteam:
        lines.append(
            f"| Red-team attacks handled safely | {redteam['passed']} of {redteam['total']} |"
        )
    lines += [
        f"| Audit hash chains verified | {metrics['chains_verified']} of "
        f"{metrics['audit_logs']} ({metrics['audit_events']} events) |",
        f"| Sandbox orders filled, each after a Confirm click | {metrics['orders_filled']} |",
        f"| Automated tests passing / line coverage | {metrics['tests_passed']} / "
        f"{metrics['coverage_pct']}% |",
    ]
    if metrics.get("median_suite_reply_ms"):
        lines.append(
            f"| Typed reply time, median / 90th percentile | "
            f"{metrics['median_suite_reply_ms'] / 1000:.0f} s / "
            f"{metrics['p90_suite_reply_ms'] / 1000:.0f} s ({metrics['suite_replies']} turns) |"
        )
    lines.append(f"| Button reply time, median | {metrics['median_button_reply_ms']:.0f} ms |")
    lines += [
        "",
        "## 2. Automated tests",
        "",
        "Run on every push by CI (`.github/workflows/ci.yml`) with format, lint, strict typing "
        "and the layer contracts. Command: `npm run test:server`.",
        "",
        "| File | What it covers |",
        "|---|---|",
        "| `tests/policy/test_policy.py` | An allow and a deny test for every rule (`STAGE-01`, "
        "`READY-01/02`, `SUIT-01`, `CONC-01`, `LIM-01`, `CONF-01`, `COOL-01`, `LANG-*`); "
        "confirmation tokens: missing, forged, other key, other proposal, changed proposal, "
        "expired, reused |",
        "| `tests/audit/test_audit.py` | The hash chain catches an edited, deleted or reordered "
        "line, broken JSON, a forged re-hashed link and a fully rewritten file; parallel "
        "appends keep it intact |",
        "| `tests/engine/` | Readiness, savings plan, risk scoring, suitability, allocation, "
        "bootstrap ranges and drift, including property tests |",
        "| `tests/agent/test_guards_and_wiring.py` | Input guard, output filter, tool offering "
        "per stage, provider fallback chains, failures and timeouts, the tool-call limit |",
        "| `tests/api/test_personas.py` | The three personas and their edge cases through every "
        "API route |",
        "| `tests/core/test_reference.py` | The reference data loads and is consistent |",
        "",
        "End-to-end: Playwright clicks through the three personas in a real browser at 1280px "
        "and 390px (`client/e2e/personas.spec.ts`, `npm run test:e2e`).",
        "",
    ]
    if tasks:
        lines += _tasks(tasks)
    if redteam:
        lines += _redteam(redteam)
    if personas:
        lines += _personas(personas)
    lines += [
        "## 6. Found and fixed",
        "",
        "Reading the real-model transcripts found these problems. Each was traced, fixed in "
        "code and re-run. None was unsafe: in every case the guardian bounded what the mistake "
        "could do, so a miss was a missed action, never a wrong order.",
        "",
        "| Found | Fix |",
        "|---|---|",
        *[f"| {_cell(found)} | {_cell(fix)} |" for found, fix in FIXES],
        "",
        "## 7. How to reproduce",
        "",
        "```bash",
        "npm run setup",
        "# set LLM_PROVIDER=google, GOOGLE_GENERATIVE_AI_API_KEY and GEMINI_MODEL in server/.env",
        "npm run evidence:llm     # tasks, red team, personas, chains, metrics, figure",
        "cd server && .venv/bin/python scripts/test_report.py",
        "```",
        "",
        "A free model is not deterministic, so a re-run can differ by a task or two. Without a "
        "key, `npm run evidence` runs the same suites on the scripted model.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    """Write the report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=SERVER_DIR / "evidence" / "gemma")
    args = parser.parse_args()
    metrics = _load(args.evidence / "metrics.json")
    if metrics is None:
        raise SystemExit(f"run metrics.py --out {args.evidence} first")
    report = build(
        metrics,
        _load(args.evidence / "tasks.json"),
        _load(args.evidence / "redteam.json"),
        _load(args.evidence / "personas.json"),
    )
    OUT.write_text(report, encoding="utf-8")
    print(f"wrote {OUT.relative_to(SERVER_DIR.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
