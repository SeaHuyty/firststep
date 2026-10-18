"""Run the three demo personas end to end and keep their audit logs.

    python scripts/run_personas.py          # scripted fake LLM
    python scripts/run_personas.py --llm    # the provider in server/.env

Writes evidence/logs/{amina,leo,mei}.jsonl (hash-chained audit logs) and
evidence/personas.md. Leo's run includes a blocked order (LIM-01) and a
blocked panic sale (COOL-01); Mei's includes a blocked unsuitable mix.
"""

import argparse
import shutil
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import AMINA, LEO, LEO_GOAL, MEI, MEI_GOAL, Session, make_client, write_json

SERVER_DIR = Path(__file__).resolve().parents[1]
EXTRA: dict[str, Session] = {}  # extra sessions whose logs are kept as evidence too


def amina(client: Any) -> tuple[Session, list[str]]:
    """Run Amina: not ready, so a savings plan and no portfolio."""
    s = Session(client, "amina")
    s.answer_all(AMINA)
    plan = s.cards("savings_plan")[0]
    s.say("Can I invest anyway?")
    return s, [
        f"Stage: {s.last['stage']} (READY-01 and READY-02 failed)",
        f"Savings plan: {len(plan['steps'])} steps, ready by {plan['ready_month']}",
    ]


def leo(client: Any) -> tuple[Session, list[str]]:
    """Run Leo: C3 plan, confirmed orders, March 2020, a sale that waits."""
    s = Session(client, "leo")
    s.answer_all(LEO)
    s.act("set_goal", **LEO_GOAL)
    s.say("What does diversification mean?")
    s.act("prepare_orders")
    s.confirm()
    fills = len(s.cards("receipt")[0]["fills"])
    s.act("advance_time", until="2020-03")
    s.say("Sell everything now!")
    paused = [c["rule_id"] for c in s.cards("pause")]
    s.act("advance_time", months=12)
    value = s.cards("portfolio")[-1]
    # A second goal with a large lump sum shows the per-order limit.
    big = Session(client, "leo")
    big.answer_all(LEO)
    big.act("set_goal", **{**LEO_GOAL, "lump_sum_usd": 50000})
    big.act("prepare_orders")
    lim = [c["rule_id"] for c in big.cards("refusal")]
    EXTRA["leo-limit"] = big
    return s, [
        f"Confirmed {fills} sandbox orders ($6,000) and a $300 monthly plan",
        f"March 2020: panic sale paused by {', '.join(paused) or 'nothing'}",
        f"March 2021: value ${float(value['value_usd']):,.2f}, paid in ${float(value['paid_in_usd']):,.2f}",
        f"$50,000 at once: refused by {', '.join(lim) or 'nothing'}",
    ]


def mei(client: Any) -> tuple[Session, list[str]]:
    """Run Mei: C2; all-in tech refused; the C2 plan offered."""
    s = Session(client, "mei")
    s.answer_all(MEI)
    s.act("set_goal", **MEI_GOAL)
    s.say("Put everything in tech stocks. They always go up.")
    refused = [c["rule_id"] for c in s.cards("refusal")]
    offer = s.cards("allocation")
    return s, [
        f"Risk class: C2; all-in tech refused by {', '.join(refused) or 'nothing'}",
        f"Offered instead: {offer[0]['label'] if offer else 'nothing'}",
    ]


def main() -> int:
    """Run all personas and write the evidence."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--llm", action="store_true", help="use the real provider from .env")
    parser.add_argument("--out", type=Path, default=SERVER_DIR / "evidence")
    args = parser.parse_args()
    run_dir = args.out / "run" / "personas"
    shutil.rmtree(run_dir, ignore_errors=True)
    logs = args.out / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {}
    with make_client(run_dir, real_llm=args.llm) as client:
        provider = client.app.state.llm_provider  # type: ignore[attr-defined]
        for name, run in (("amina", amina), ("leo", leo), ("mei", mei)):
            print(f"{name}: running…", flush=True)
            session, notes = run(client)
            check = session.audit()["check"]
            shutil.copy(run_dir / "logs" / f"{session.id}.jsonl", logs / f"{name}.jsonl")
            summary[name] = {
                "notes": notes,
                "events": check["events"],
                "chain_ok": check["ok"],
                "head": check["head"],
            }
        for name, extra in EXTRA.items():
            shutil.copy(run_dir / "logs" / f"{extra.id}.jsonl", logs / f"{name}.jsonl")
    write_json(args.out / "personas.json", {"llm": provider, "personas": summary})
    lines = [
        "# Persona runs",
        "",
        f"LLM: `{provider}`. Audit logs: `evidence/logs/<name>.jsonl`; verify with "
        "`python scripts/verify_chain.py evidence/logs/*.jsonl`.",
        "",
    ]
    for name, data in summary.items():
        lines += [f"## {name.title()}", ""]
        lines += [f"- {n}" for n in data["notes"]]
        lines += [
            f"- Audit log: {data['events']} events, chain {'verified' if data['chain_ok'] else 'BROKEN'}, head `{data['head'][:16]}…`",
            "",
        ]
    (args.out / "personas.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 0 if all(d["chain_ok"] for d in summary.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
