# 40 条盲标操作指南

完整版说明书见仓库 `docs/annotation-manual.md`（可打印版 `docs/annotation-manual.docx`）。  
用另一个模型做第二标注：见 `tests/annotation/MODEL_ANNOTATION_PROMPT.md`；它只能算模型-模型一致率，不能替代人工验证。

## 目标

独立判断这 40 条文献是否应纳入，用于人-模型一致率（Cohen's κ）。  
**不要看** `tests/gold/seed_labels.json`、`runs/*.semantic*`、`tests/make_semantic_*`。  
只看 `annotation_packet.csv` 里的 title、evidence、type 和 checks。

时间：约 90–120 分钟；可以按 topic 分三次做。

## 三个题目

| source_run | 题目 |
|---|---|
| materials | perovskite interface passivation |
| social | undergraduate research training |
| chinese | 乡村振兴 + 数字治理 |

## 每行填 7 列

| 列 | 填法 |
|---|---|
| `verdict` | `✓` 纳入 / `×` 排除 / `○` 待核 |
| `reason_code` | `✓` 留空；`×` 填 R1/P1/Y1/L1/V1/T1/S1/M1/C1/I1；`○` 填 D1/D2/D3/D4/E1 |
| `category` | `primary` / `review` / `background` / `preprint` |
| `one_liner` | 一句话，非空，≤24 字 |
| `evidence_quote` | `✓` 和语义 `×` 必填：从 evidence/title 复制一段逐字原文 |
| `confidence_1_5` | 1–5；3 以下说明拿不准 |
| `notes` | 可选：为什么难判、边界情况 |

## 判定顺序（first-fail）

```text
主题 → 体系/对象 → 手段/方法 → 条件/情境 → 指标/结果
```

- **T1 主题不符**：应用场景/研究问题不是这个题目。例：钙钛矿用于光解水、光电探测器；乡村振兴但只谈公路管理。
- **S1 体系/对象不符**：同一主题，但器件/材料/样本不同。例：钙钛矿忆阻器 vs 钙钛矿太阳能电池。
- **M1 手段/方法不符**：同一对象，但研究手段不同。例：表面掺杂、缺陷工程、载流子管理、测复合速度，而不是界面钝化。
- **C1 条件/情境不符**：同一手段，但温度/浓度/规模/地区/政策情境不同。
- **I1 指标/结果不符**：同一条件，但效率/稳定性/精度/变量口径不同。
- **元数据码**：R1 撤稿；P1 类型不符；Y1 年份越界；L1 语言不符；V1 版本重复。
- **待核码**：D1 无 DOI；D2 DOI 无法解析；D3 标题不一致；D4 核验服务不可用；E1 证据不足。
- **background_candidate=true**：按 review/background 处理，不受 Y1 限制；主题不符仍 T1/S1。

## 三条容易吵的边界

1. **综述/观点/Preview**  
   不是 primary。`category` 填 `review` 或 `background`，`verdict` 可以是 `✓`，但**不计入 K**。  
   如果它明显是另一个主题的综述，仍按 `T1`/`S1` 排除。

2. **摘要为空**  
   标题能判主题；但对象/方法/条件/指标没有 evidence。  
   primary research 一律 `○ E1`，不要凭标题硬判 `✓`。  
   综述/观点可在标题明确时判 `✓ B`。

3. **无 DOI 但主题明显不符**  
   first-fail 先判语义：主题/对象/方法不符 → `× T1/S1/M1`；不要因为无 DOI 就一律 `D1`。  
   主题相关但无 DOI → `○ D1`。

## 怎么填 evidence_quote

- 从 `evidence` 里复制**完整一句**，不要改写、不要翻译、不要加省略号。
- 如果 evidence 为空，`✓ B` 可以用 `title` 作为 quote；`○ E1` 可以留空。
- 如果 quote 不在 evidence/title 里，模型审计会报错。

## 标完后评分

```bash
python tests/score_annotation.py \
  --labels tests/annotation/annotation_packet.csv \
  --reference tests/gold/seed_labels.json
```

输出：verdict/reason/category 一致率，verdict/reason 的 Cohen's κ，以及不一致条目。  
参考标签是开发期 seed，不是第二个人工标注；这里算的是**人-模型一致率**，不是人-人一致率。  
如果能找到第二位同学独立标同一份，另存为 `personB.csv`，用：

```bash
python tests/score_annotation.py --labels personA.csv --reference personB.csv
```

这才是验收要的人-人 κ。

## 验收线

- verdict 一致率 ≥0.80。
- verdict κ ≥0.60。
- 如果 κ 低，先看 reason_code 的混淆矩阵，优先修 M1/T1/S1 边界，不要直接改模型。
