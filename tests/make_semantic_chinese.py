"""Semantic judgments for the Chinese run (rural revitalization + digital governance)."""

import json
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

JUDGMENTS = {
    1: ("✓", "", "primary", "数字治理，直接相关"),
    2: ("×", "T1", "primary", "公路管理，非数字治理"),
    3: ("○", "E1", "primary", "摘要缺失，待读全文"),
    4: ("○", "E1", "primary", "摘要缺失，待读全文"),
    5: ("✓", "", "primary", "数据融合方法"),
    6: ("×", "T1", "primary", "数字经济，非数字治理"),
    7: ("✓", "", "primary", "西安数字治理"),
    8: ("○", "E1", "primary", "摘要缺失，待读全文"),
    9: ("✓", "", "primary", "数字治理与电商"),
    10: ("✓", "", "primary", "三资数字治理"),
    11: ("✓", "", "primary", "含数字治理路径"),
    12: ("○", "D1", "primary", "无 DOI，先别引用"),
    13: ("○", "E1", "primary", "摘要缺失，待读全文"),
    14: ("✓", "", "primary", "数字技术赋能"),
    15: ("×", "T1", "primary", "科技特派员，非数字治理"),
    16: ("✓", "", "primary", "邳州数字治理"),
    17: ("✓", "", "primary", "社区数字治理"),
    18: ("✓", "", "primary", "治理碎片化"),
    19: ("×", "T1", "primary", "法治，非数字治理"),
    20: ("✓", "", "primary", "河南数字乡村"),
    21: ("×", "T1", "primary", "千万工程，非数字治理"),
    22: ("✓", "", "primary", "垃圾分类治理"),
    23: ("✓", "", "primary", "社会资本视角"),
    24: ("×", "T1", "primary", "协商治理，非数字治理"),
    25: ("✓", "", "primary", "环境行为治理"),
    26: ("✓", "", "background", "背景综述"),
    27: ("✓", "", "background", "背景评估"),
    28: ("✓", "", "background", "背景研究"),
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
