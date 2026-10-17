"""Verify hash-chained audit logs.

    python scripts/verify_chain.py evidence/logs/*.jsonl

Prints OK with the event count and latest hash for each file, or the
first broken sequence number and why. Exits 1 if any file is broken.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.audit.verify import verify_lines


def main() -> int:
    """Verify every file given and return the exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logs", nargs="+", type=Path)
    parser.add_argument("--head", help="expected latest hash, anchored outside the file")
    args = parser.parse_args()

    broken = 0
    for path in args.logs:
        result = verify_lines(path.read_text(encoding="utf-8").splitlines(), args.head)
        if result.ok:
            print(f"OK      {path.name}: {result.events} events, head {result.head[:16]}…")
        else:
            broken += 1
            where = "" if result.first_bad_seq is None else f" at seq {result.first_bad_seq}"
            print(f"BROKEN  {path.name}{where}: {result.reason}")
    return 1 if broken else 0


if __name__ == "__main__":
    raise SystemExit(main())
