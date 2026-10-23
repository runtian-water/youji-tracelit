# 测试与评估资产

## 一键运行

```bash
python -m unittest discover -s tests -v        # 42 项单测，离线，不需要 key
```

## 文件说明

| 文件 | 作用 | 是否需要网络 |
|---|---|---|
| `test_core.py` | 命令行、门禁、计数、GB/T、docx、提示词注入防护等 42 项单测 | 否（mock/固定响应） |
| `eval_gold.py` | 对 `gold/seed_labels.json` 做趋势回归；默认不设硬门禁 | 否 |
| `score_annotation.py` | 盲标 CSV/JSON 的一致率与 Cohen's κ | 否 |
| `cases.md` | 手工验收案例（失败模式、边界） | 可能 |
| `make_judgments.py` | 生成机械冒烟 judgments（`mode=mechanical_smoke`），**不是语义判定** | 否 |
| `make_semantic_*.py` | 开发期生成 seed 语义判定的脚本；产出与 seed 同源，不能当独立验证 | 否 |
| `gold/seed_labels.json` | 84 条开发期回归标签 | 否 |
| `annotation/` | 40 条盲标包、说明书与模型提示词 | 否 |
| `blind/` | materials 28 条盲评输入与提示词 | 否 |
| `fixtures/` | 单测用的最小输入/输出 | 否 |

## 常用命令

```bash
# 对示例判定做回归（趋势记录）
python tests/eval_gold.py --run materials \
  --judgments examples/judgments/materials.semantic.json
python tests/eval_gold.py --run social \
  --judgments examples/judgments/social.semantic.json
python tests/eval_gold.py --run chinese \
  --judgments examples/judgments/chinese.semantic.json

# 人工盲标 vs seed
python tests/score_annotation.py \
  --labels tests/annotation/annotation_packet.csv \
  --reference tests/gold/seed_labels.json

# 两位人工标注：人-人 κ
python tests/score_annotation.py --labels personA.csv --reference personB.csv
```

## 结果怎么表述

| 比较 | 能写成 | 不能写成 |
|---|---|---|
| seed vs seed | 回归通过 | 准确率 |
| 模型 vs seed | 模型-seed 一致率 | 人工验证 |
| 模型 vs 模型 | 模型-模型一致率 | 人-人 κ |
| 人工 vs seed | 人-模型一致率 | 人-人 κ |
| 人工 vs 人工 | 人-人 κ | 语义绝对正确 |

## 不要提交

- `__pycache__/`、`*.pyc`；
- `runs/` 原始产物（需要保留的判定复制到 `examples/judgments/`）；
- 未脱敏的人工标注草稿；
- 任何含 API key 的文件。
