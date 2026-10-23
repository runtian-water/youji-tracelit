"""Semantic judgments for the materials run (perovskite interface passivation).

This is a human/LLM semantic pass, not a mechanical smoke test.
"""

import json
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

# rank: (verdict, reason_code, category, one_liner)
JUDGMENTS = {
    1: ("✓", "", "primary", "界面钝化，直接相关"),
    2: ("✓", "", "primary", "表面钝化，直接相关"),
    3: ("✓", "", "primary", "NiOx 界面钝化"),
    4: ("✓", "", "background", "综述，作背景"),
    5: ("✓", "", "background", "Perspective，作背景"),
    6: ("×", "M1", "primary", "表面掺杂，非钝化"),
    7: ("×", "S1", "primary", "忆阻器器件，非光伏"),
    8: ("✓", "", "primary", "协同钝化，直接相关"),
    9: ("×", "T1", "review", "水分解应用，非钝化"),
    10: ("✓", "", "background", "综述，作背景"),
    11: ("✓", "", "background", "Preview，作背景"),
    12: ("✓", "", "primary", "CsI 表面钝化"),
    13: ("×", "M1", "primary", "体相缺陷工程，非界面"),
    14: ("×", "M1", "primary", "测复合速度，非钝化"),
    15: ("○", "E1", "primary", "摘要缺失，待读全文"),
    16: ("✓", "", "primary", "钝化与卤素偏析"),
    17: ("✓", "", "background", "观点文，作背景"),
    18: ("✓", "", "primary", "叠层界面钝化"),
    19: ("✓", "", "background", "Perspective，作背景"),
    20: ("○", "D1", "primary", "无 DOI，先别引用"),
    21: ("×", "M1", "primary", "载流子管理，非钝化"),
    22: ("✓", "", "background", "综述，作背景"),
    23: ("○", "E1", "primary", "摘要缺失，待读全文"),
    24: ("✓", "", "primary", "Lewis 碱界面钝化"),
    25: ("×", "T1", "review", "光电探测器，非钝化"),
    26: ("✓", "", "background", "背景综述"),
    27: ("✓", "", "background", "背景综述"),
    28: ("✓", "", "background", "背景综述"),
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
