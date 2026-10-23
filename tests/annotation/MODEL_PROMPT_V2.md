# Model B v2 prompt — 40-record blind annotation

把下面整段提示词和 `tests/annotation/annotation_packet.json` 一起发给另一个模型。  
如果对方不能读文件，把 `annotation_packet.json` 的内容贴在提示词末尾。

---

```text
你是一名独立的文献筛选标注员。请只依据我提供的 40 条记录做判断，不要使用任何外部记忆补充文献。

数据文件：annotation_packet.json（40 条；字段包括 record_id、topic、title、year、type、
background_candidate、doi、evidence、evidence_field、year_ok、type_ok、language_ok、
retracted_ok、version_ok、verification_status、verification_reason）。

禁止读取或使用：
- tests/gold/seed_labels.json
- runs/*.semantic*
- tests/make_semantic_*
- 任何已有模型/人工标签
这些是参考标签，会破坏盲标。

## 三个题目

1. materials：perovskite interface passivation
2. social：undergraduate research training
3. chinese：乡村振兴 + 数字治理

## 判定顺序（first-fail，只记一个主因）

R1 → P1 → Y1 → L1 → V1 → T1 → S1 → M1 → C1 → I1 → D1 → D2/D3/D4 → E1

先看元数据：撤稿、类型、年份、语言、版本。
再看语义：主题 → 体系/对象 → 手段/方法 → 条件/情境 → 指标/结果。
最后看 DOI、核验、证据。

## 题目专属规则

### materials
- 必须同时命中：钙钛矿/卤化物钙钛矿 + 界面/表面钝化。
- 光解水、光电探测器等应用不同 → T1。
- 忆阻器等器件/对象不同 → S1。
- 表面掺杂、缺陷工程、载流子管理、只测复合速度 → M1。
- 纯综述/Perspective/Preview → category review/background，可 ✓ B，不计 K。

### social
- 主题是本科研究训练/经历/导师制；其他主题 → T1。
- 书评、会议前言、paratext → × P1。
- 摘要为空的 primary research → ○ E1；不要凭标题硬判 ✓。
- 综述/经典背景 → category review/background，可 ✓ B。

### chinese
- 必须同时命中：乡村振兴 + 数字治理。只命中一半 → T1。
- 以下只算“乡村振兴”一侧：公路管理、数字经济、科技特派员、法治、千万工程、协商治理 → T1。
- 主题相关但无 DOI → ○ D1；主题不符先判 T1/S1/M1。
- 摘要为空 → ○ E1（综述/背景除外）。

## 背景规则

- `background_candidate=true`：按 review/background 处理，**不受 Y1 限制**；主题不符仍 T1/S1。
- 综述、Perspective、Preview、评论：不要填 primary。
- 背景/综述可以 ✓，但计入 B，不计入 K。

## 符号

- verdict：✓ 纳入 / × 排除 / ○ 待核
- reason_code：
  - ×：R1/P1/Y1/L1/V1/T1/S1/M1/C1/I1
  - ○：D1/D2/D3/D4/E1
  - ✓：留空
- category：primary / review / background / preprint
- evidence_quote：✓ 和语义 ×（T1/S1/M1/C1/I1）必填，必须是 evidence/title 的逐字子串
- one_liner：非空，≤24 字
- confidence_1_5：1–5
- notes：可选

## 输出

只输出 JSON，写到 runs/modelB2.semantic.json。如果无法写文件，直接输出 JSON 正文，不要加解释：

{
  "mode": "semantic",
  "records": [
    {
      "openalex_id": "W...",
      "verdict": "✓|×|○",
      "reason_code": "",
      "category": "primary|review|background|preprint",
      "evidence_quote": "逐字片段",
      "one_liner": "≤24 字",
      "confidence_1_5": 3,
      "notes": ""
    }
  ]
}

覆盖全部 40 条 openalex_id，不得遗漏或新增。
不要编造 evidence；引文必须能在 evidence/title 中找到。
不确定时用 ○ E1，并在 notes 写原因，不要硬判 ✓。

## 输出前自检

- 40 条都有 verdict。
- 每个 ×/○ 的理由码在允许集合内。
- 每个 ✓ 的 reason_code 为空。
- 每个 category 合法。
- 每个 one_liner 非空且 ≤24 字。
- 每个 ✓ 和语义 × 都有逐字 evidence_quote。
- 没有使用任何参考标签。
```

---

## 评分

```bash
python tests/score_annotation.py \
  --labels runs/modelB2.semantic.json \
  --reference tests/gold/seed_labels.json
```

模型-模型：

```bash
python tests/score_annotation.py \
  --labels runs/modelB.semantic.json \
  --reference runs/modelB2.semantic.json
```

模型-人工：

```bash
python tests/score_annotation.py \
  --labels runs/modelB2.semantic.json \
  --reference personA.csv
```
