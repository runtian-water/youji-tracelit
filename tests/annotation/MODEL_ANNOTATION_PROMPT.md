# 用另一个模型做第二标注（模型-模型核验）

> 推荐使用 v3：`tests/annotation/MODEL_PROMPT_V3.md`（含修正后的 `background_candidate`、三个题目的专属规则、上次错误清单和自检）。本文件保留为简版。

## 这能证明什么

- 能证明：同一批文献上，两个模型的判断是否稳定、是否共享同一种偏差。
- 不能证明：模型判断正确；也不能替代人-人 κ。
- 结论只能写成“模型-模型一致率”，不能写成“人工验证通过”。

## 给另一个模型的提示词

把下面内容连同 `annotation_packet.json`（或 CSV）发给另一个模型。  
要求它**不要读取** `tests/gold`、`runs/*.semantic*`、`tests/make_semantic_*`。

```text
你是独立的文献筛选标注员。请读取：
- tests/annotation/annotation_packet.json
- docs/annotation-manual.md（或 tests/annotation/ANNOTATION_GUIDE.md）

不要读取 tests/gold、runs/*.semantic、tests/make_semantic_*；那些是参考标签。

任务：对 40 条文献逐条判断是否纳入。按 first-fail：
R1 → P1 → Y1 → L1 → V1 → T1 → S1 → M1 → C1 → I1 → D1 → D2/D3/D4 → E1。

字段：
- verdict: ✓ / × / ○
- reason_code: ✓ 留空；× 用排除码；○ 用待核码
- category: primary / review / background / preprint
- evidence_quote: ✓ 和语义 × 必填，必须是 evidence/title 的逐字子串
- one_liner: 非空，≤24 字
- confidence_1_5: 1–5
- notes: 可选

输出 JSON，写到 runs/modelB.semantic.json：
{
  "mode": "semantic",
  "records": [
    {
      "openalex_id": "W...",
      "verdict": "✓|×|○",
      "reason_code": "",
      "category": "primary|review|background|preprint",
      "evidence_quote": "...",
      "one_liner": "≤24 字",
      "confidence_1_5": 3,
      "notes": ""
    }
  ]
}

覆盖全部 40 条；不要遗漏，不要编造 evidence。完成只回复：done。
```

## 标完怎么算

模型-模型（两份 JSON/CSV 任选）：

```bash
python tests/score_annotation.py \
  --labels runs/modelA.semantic.json \
  --reference runs/modelB.semantic.json
```

模型-人工：

```bash
python tests/score_annotation.py \
  --labels runs/modelB.semantic.json \
  --reference personA.csv
```

模型-开发 seed（只作趋势）：

```bash
python tests/score_annotation.py \
  --labels runs/modelB.semantic.json \
  --reference tests/gold/seed_labels.json
```

## 注意

- 两个模型最好来自不同实验室/厂商；同家族模型的一致性会偏高。
- 模型可能比人更“乐观”，容易把边缘文献判 ✓；重点看 `E1`、`S1/M1`、`B` 的差异。
- 模型给的 `confidence` 不是校准过的概率，只作参考。
- 如果模型输出无法通过 `evidence_quote` 校验，先修格式，不要直接拿来算一致率。
