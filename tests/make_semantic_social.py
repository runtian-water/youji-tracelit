"""Semantic judgments for the social-science run (undergraduate research training)."""

import json
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

JUDGMENTS = {
    1: ("✓", "", "primary", "AHA 项目，直接相关"),
    2: ("✓", "", "background", "书目，作背景"),
    3: ("✓", "", "primary", "URE 多样性，相关"),
    4: ("✓", "", "primary", "CSURE 项目，相关"),
    5: ("○", "E1", "primary", "摘要缺失，待读全文"),
    6: ("○", "E1", "primary", "摘要缺失，待读全文"),
    7: ("✓", "", "primary", "师生发表，相关"),
    8: ("×", "P1", "primary", "类型 other，非论文"),
    9: ("✓", "", "primary", "地球物理项目"),
    10: ("✓", "", "primary", "培训工作坊"),
    11: ("○", "E1", "primary", "摘要缺失，待读全文"),
    12: ("✓", "", "primary", "EECS 留存"),
    13: ("✓", "", "primary", "BME 项目"),
    14: ("✓", "", "primary", "M-CURE 项目"),
    15: ("✓", "", "primary", "转学生 URE"),
    16: ("✓", "", "primary", "工程研究生"),
    17: ("✓", "", "primary", "导师实践"),
    18: ("✓", "", "primary", "加速培训"),
    19: ("✓", "", "primary", "研究概念化"),
    20: ("✓", "", "primary", "植物纳米化学"),
    21: ("✓", "", "primary", "远程结构化"),
    22: ("×", "P1", "primary", "书评，非论文"),
    23: ("○", "E1", "primary", "摘要缺失，待读全文"),
    24: ("✓", "", "primary", "导师包容"),
    25: ("○", "E1", "primary", "摘要缺失，待读全文"),
    26: ("✓", "", "background", "背景综述"),
    27: ("✓", "", "background", "背景综述"),
    28: ("×", "P1", "primary", "会议前言，非论文"),
}


def main(path: str):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    records = []
    for rec in data.get("records") or []:
        verdict, code, category, one = JUDGMENTS[rec["rank"]]
        records.append({
            "openalex_id": rec.get("openalex_id"),
            "title": rec.get("title"),
            "year": rec.get("year"),
            "type": rec.get("type"),
            "doi": rec.get("doi"),
            "verdict": verdict,
            "reason_code": code,
            "category": category,
            "evidence_quote": (
                (rec.get("evidence") or "").strip()[:160]
                or (rec.get("title") or "").strip()[:160]
            ),
            "one_liner": one,
        })
    print(json.dumps({"mode": "semantic", "records": records}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main(sys.argv[1])
