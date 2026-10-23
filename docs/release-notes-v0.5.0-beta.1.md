# TraceLit v0.5.0-beta.1

**Beta / research prototype.** 不写综述、不判定创新性、不提供全文。

## 功能

- 三档：寻迹 / 循迹 / 溯迹（facet 计数、Top5、缺口阈值）。
- OpenAlex 实时检索；Crossref/DataCite DOI 核验；429/预算/key 处理。
- 8 列审计表、理由码、B/P 分节、GB/T 7714、复现块、成本、固定尾注、CNKI 提示。
- 语义门禁：`mode` 白名单 + `evidence_quote` 逐字校验 + `one_liner` ≤24。
- `run` 一条命令；`docx` 导出 A4 Word。
- CI、MIT License、40 条盲标包、seed gold 回归、盲标说明书。
- `examples/judgments/` 附三组语义判定和模型 B/B2/B3 复核结果。

## 验证现状

- 42 项单测通过。
- 三次盲评（materials 28 条）：verdict 0.857–0.929，exact triple 0.679–0.750，drift 7.1–10.7%。
- 另一个模型（修正 packet，40 条）：vs seed verdict 0.95，κ 0.92；仅 2 条 B/T1 边界争议。
- 人-人 κ **未测**。

## 不能宣称

- 不是 v1.0。
- 不是系统综述。
- 不能证明“没人做过”。
- 语义准确率仍在验证；`✓` 只代表 DOI/标题/年份核验 + 当轮语义判断，不代表内容优质。

## 安装

```bash
git clone https://github.com/<你的用户名>/youji-tracelit.git ~/.claude/skills/tracelit
cd ~/.claude/skills/tracelit
cp .env.example .env   # 填 OPENALEX_API_KEY
python scripts/main.py doctor --tier 循迹
```

目录名必须保持 `tracelit`，与 `SKILL.md` 的 `name` 一致。

## 已知限制

- 中文期刊 OpenAlex 覆盖有限，需 CNKI/万方补充。
- 专利/标准/全文不在覆盖范围。
- 默认 facet/Top5 是词面，不冒充语义匹配。
- 语义判定需人工复核；v1.0 需独立人工 κ。
- `tests/gold/seed_labels.json` 是开发期回归集，不是独立验证。
