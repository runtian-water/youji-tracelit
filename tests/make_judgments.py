"""Mechanical smoke-test judgments from checks + verification.

This is NOT the semantic judgment the skill expects from the LLM.
It exists only to exercise audit/render end-to-end with real API data.
"""

import json
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass


def judge(rec):
    checks = rec.get("checks") or {}
    verification = rec.get("verification") or {}
    if checks.get("retracted_ok") is False:
        return "×", "R1"
    if checks.get("type_ok") is False:
        return "×", "P1"
    if rec.get("category") in ("review", "background"):
        if verification.get("status") == "pass":
            return "✓", ""
        if verification.get("reason") == "no_doi":
            return "○", "D1"
        if verification.get("status") == "unavailable":
            return "○", "D4"
        return "○", "E1"
    if checks.get("year_ok") is False:
        return "×", "Y1"
    if checks.get("language_ok") is False:
        return "×", "L1"
    if checks.get("version_ok") is False:
        return "×", "V1"
    if verification.get("status") == "pass":
        return "✓", ""
    reason = verification.get("reason")
    if reason == "no_doi":
        return "○", "D1"
    if reason == "doi_not_found":
        return "○", "D2"
    if verification.get("status") == "unavailable":
        return "○", "D4"
    return "○", "E1"


def main(path: str):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    out = []
    for rec in data.get("records") or []:
        verdict, code = judge(rec)
        out.append({
            "openalex_id": rec.get("openalex_id"),
            "title": rec.get("title"),
            "year": rec.get("year"),
            "type": rec.get("type"),
            "doi": rec.get("doi"),
            "verdict": verdict,
            "reason_code": code,
            "category": rec.get("category", "primary"),
            "evidence_quote": (
                (rec.get("evidence") or "").strip()[:120]
                or (rec.get("title") or "").strip()[:120]
            ),
            "one_liner": "[机械冒烟] 未做语义判定",
        })
    print(json.dumps({
        "mode": "mechanical_smoke",
        "records": out,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main(sys.argv[1])
