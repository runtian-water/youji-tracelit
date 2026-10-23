# 语义判定 JSON

这些文件是 2026-10-22 开发期运行的判定结果，用来让 `eval_gold.py`、`score_annotation.py` 和示例报告可复现。它们**不是**独立人工标注。

| 文件 | 来源 | 用途 |
|---|---|---|
| `materials.semantic.json` | materials 检索 + seed 语义判定 | 对应 `examples/materials.semantic.report.md` |
| `social.semantic.json` | social 检索 + seed 语义判定 | 对应 `examples/social.semantic.report.md` |
| `chinese.semantic.json` | chinese 检索 + seed 语义判定 | 对应 `examples/chinese.semantic.report.md` |
| `modelB.semantic.json` | 另一个模型标注 40 条（早期 packet） | `docs/modelB-results.md` 的 B 轮 |
| `modelB2.semantic.json` | 同一模型重跑（早期 packet） | B2 轮；受 packet flag bug 影响 |
| `modelB3.semantic.json` | 修正 packet 后的重跑 | B3 轮；当前最好结果，仍是模型-seed |

## 结构

`mode=semantic`，`records` 为数组；每条至少含：

```json
{
  "openalex_id": "W...",
  "verdict": "✓ | × | ○",
  "reason_code": "T1 等；✓ 可空",
  "category": "primary | review | background | preprint",
  "one_liner": "≤24 字",
  "evidence_quote": "从 evidence/title 逐字复制"
}
```

## 重新评分

```bash
python tests/eval_gold.py --run materials \
  --judgments examples/judgments/materials.semantic.json

python tests/score_annotation.py \
  --labels examples/judgments/modelB3.semantic.json \
  --reference tests/gold/seed_labels.json
```

注意：seed 标签和这些判定同源于开发过程；用它算出的分数只能用于回归和趋势，不能对外宣称准确率或人工验证。
