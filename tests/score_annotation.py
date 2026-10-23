"""Score a filled 40-record annotation CSV against reference labels.

This is human-vs-model agreement against the development seed labels. It is not
human-vs-human agreement; use two independently filled CSVs for that.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass


def kappa(pairs: list[tuple[str, str]]) -> float | None:
    if not pairs:
        return None
    n = len(pairs)
    po = sum(a == b for a, b in pairs) / n
    labels = {a for a, _ in pairs} | {b for _, b in pairs}
    pe = sum(
        (sum(1 for a, _ in pairs if a == label) / n)
        * (sum(1 for _, b in pairs if b == label) / n)
        for label in labels
    )
    if pe >= 1:
        return 1.0
    return round((po - pe) / (1 - pe), 4)


def agreement(pairs: list[tuple[str, str]]) -> float | None:
    if not pairs:
        return None
    return round(sum(a == b for a, b in pairs) / len(pairs), 4)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", default="tests/annotation/annotation_packet.csv")
    parser.add_argument("--reference", default="tests/gold/seed_labels.json")
    parser.add_argument("--strict", action="store_true", help="exit 1 below verdict 0.80 or kappa 0.60")
    args = parser.parse_args()

    ref_path = Path(args.reference)
    if ref_path.suffix.lower() == ".csv":
        with ref_path.open(encoding="utf-8-sig", newline="") as f:
            ref_rows = list(csv.DictReader(f))
        ref = {
            r["openalex_id"]: r for r in ref_rows
            if (r.get("verdict") or "").strip()
        }
    else:
        ref_raw = json.loads(ref_path.read_text(encoding="utf-8"))
        if isinstance(ref_raw, dict):
            ref_raw = ref_raw.get("records", [])
        ref = {r["openalex_id"]: r for r in ref_raw}

    labels_path = Path(args.labels)
    if labels_path.suffix.lower() == ".json":
        raw = json.loads(labels_path.read_text(encoding="utf-8"))
        rows = raw.get("records", []) if isinstance(raw, dict) else raw
    else:
        with labels_path.open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
    filled = [r for r in rows if (r.get("verdict") or "").strip()]
    if not filled:
        print(json.dumps({
            "ok": False,
            "error": "no filled verdicts",
            "hint": "fill the verdict column in the CSV first",
        }, ensure_ascii=False, indent=2))
        return 2

    pairs = {"verdict": [], "reason_code": [], "category": []}
    mismatches = []
    missing = []
    for row in filled:
        oid = (row.get("openalex_id") or "").strip()
        gold = ref.get(oid)
        if not gold:
            missing.append(oid)
            continue
        for field in pairs:
            a = (row.get(field) or "").strip()
            b = (gold.get(field) or "").strip()
            pairs[field].append((a, b))
        exp = (gold.get("verdict") or "", gold.get("reason_code") or "", gold.get("category") or "")
        act = (row.get("verdict") or "", row.get("reason_code") or "", row.get("category") or "")
        if exp != act:
            mismatches.append({
                "record_id": row.get("record_id"),
                "openalex_id": oid,
                "expected": exp,
                "actual": act,
                "confidence": row.get("confidence_1_5"),
            })

    result = {
        "ok": True,
        "rows_total": len(rows),
        "rows_filled": len(filled),
        "compared": len(pairs["verdict"]),
        "missing_reference": missing,
        "agreement": {k: agreement(v) for k, v in pairs.items()},
        "kappa": {
            "verdict": kappa(pairs["verdict"]),
            "reason_code": kappa(pairs["reason_code"]),
        },
        "confusion_verdict": [
            {"actual": a, "reference": b, "count": n}
            for (a, b), n in Counter(pairs["verdict"]).most_common()
            if a != b
        ][:10],
        "mismatches": mismatches[:20],
        "note": (
            "human-vs-human" if ref_path.suffix.lower() == ".csv"
            else "human-vs-seed-model, not human-vs-human; seed labels are not independent"
        ),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if args.strict:
        va = result["agreement"]["verdict"] or 0
        vk = result["kappa"]["verdict"] or 0
        if va < 0.80 or vk < 0.60:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
