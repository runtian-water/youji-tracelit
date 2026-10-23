"""Compare a semantic judgments file against the seed gold labels.

This is a regression/eval harness, not independent validation: the seed labels
were authored during development and must be replaced by independent human
labels before making quality claims.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", default="tests/gold/seed_labels.json")
    parser.add_argument("--judgments", required=True)
    parser.add_argument("--run", choices=["materials", "social", "chinese"], default=None)
    parser.add_argument("--strict", action="store_true", help="非零退出码 on mismatch; default is trend-only")
    args = parser.parse_args()

    gold = json.loads(Path(args.gold).read_text(encoding="utf-8"))
    if args.run:
        gold = [g for g in gold if g.get("source_run") == args.run]
    judged_raw = json.loads(Path(args.judgments).read_text(encoding="utf-8"))
    judged = judged_raw.get("records") if isinstance(judged_raw, dict) else judged_raw
    by_id = {r.get("openalex_id"): r for r in judged}

    matches = 0
    mismatches = []
    missing = []
    for g in gold:
        j = by_id.get(g["openalex_id"])
        if not j:
            missing.append(g["openalex_id"])
            continue
        expected = (g["verdict"], g.get("reason_code") or "", g.get("category"))
        actual = (j.get("verdict"), j.get("reason_code") or "", j.get("category"))
        if expected == actual:
            matches += 1
        else:
            mismatches.append({
                "openalex_id": g["openalex_id"],
                "expected": expected,
                "actual": actual,
            })
    gold_ids = {g["openalex_id"] for g in gold}
    extra = [oid for oid in by_id if oid not in gold_ids]
    total = len(gold)
    summary = {
        "ok": not missing and not mismatches,
        "gold": args.gold,
        "run": args.run,
        "total": total,
        "matches": matches,
        "accuracy": round(matches / total, 4) if total else None,
        "missing": missing,
        "extra": extra,
        "mismatches": mismatches[:20],
        "note": "seed labels are a regression set, not independent validation",
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["ok"] or not args.strict else 1


if __name__ == "__main__":
    sys.exit(main())
