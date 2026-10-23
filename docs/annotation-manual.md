# 有迹（TraceLit）40 条盲标说明书

版本：0.5.0  
日期：2026-10-22  
用途：独立人工标注 40 条文献，计算人-模型一致率与人-人一致率。

---

## 0. 这份说明书是干什么的

你要独立判断 40 条文献“是否应纳入某个题目”，不参考模型给出的标签。  
标注结果用于回答两个问题：

1. 模型和人的判断有多一致？
2. 两个人之间的判断有多一致？

这不是“把模型结果改对”，也不是“帮模型刷分”。  
**盲标的价值在于：你先独立判断，再和模型/另一个人比对。**

---

## 1. 你会拿到什么

| 文件 | 用途 |
|---|---|
| `tests/annotation/annotation_packet.csv` | 40 条待标文献，**不含任何模型标签** |
| `tests/annotation/ANNOTATION_GUIDE.md` | 简版操作指南 |
| `tests/score_annotation.py` | 标完后计算一致率与 Cohen's κ |
| `tests/gold/seed_labels.json` | 开发期参考标签，**标注时不要打开** |
| `runs/*.semantic*` | 模型语义报告，**标注时不要打开** |

40 条构成：

- 14 条 materials：perovskite interface passivation
- 13 条 social：undergraduate research training
- 13 条 chinese：乡村振兴 + 数字治理

里面故意混入了综述、观点文、空摘要、无 DOI、单侧主题等边界样本。

---

## 2. 标什么

打开 `annotation_packet.csv`，每条文献一行。  
你只需要填 **7 列**，其余列是只读元数据：

| 列 | 必填 | 说明 |
|---|---|---|
| `verdict` | 是 | `✓` / `×` / `○` |
| `reason_code` | 是（✓ 可空） | 排除码或待核码 |
| `category` | 是 | `primary` / `review` / `background` / `preprint` |
| `one_liner` | 是 | 一句话，非空，≤24 字 |
| `evidence_quote` | ✓ 和语义 × 必填 | 从 evidence/title 逐字复制 |
| `confidence_1_5` | 是 | 1–5 |
| `notes` | 否 | 边界、犹豫原因 |

只读列：

- `record_id`、`topic`、`openalex_id`、`title`、`year`、`type`、`background_candidate`、`doi`
- `evidence`、`evidence_field`
- `year_ok`、`type_ok`、`language_ok`、`retracted_ok`、`version_ok`
- `verification_status`、`verification_reason`

---

## 3. 怎么标（逐步）

### 第 1 步：准备

1. 复制一份 `annotation_packet.csv`，命名为 `personA.csv`（保留原始空白包）。
2. 用 Excel 或 WPS 打开。
3. 选中表头，设置“冻结首行”；`evidence` 列设置“自动换行”。
4. 不要打开 `tests/gold`、`runs/*.semantic*`、`tests/make_semantic_*`。

### 第 2 步：逐条读

每条按这个顺序看：

1. `topic`：题目是什么。
2. `title`：主题是否对得上。
3. `evidence`：对象、方法、条件、指标是否对得上。
4. 元数据列：年份、类型、语言、撤稿、版本、DOI 核验状态。

### 第 3 步：判定

先走 first-fail（见第 5 节），只记一个主因。  
不确定时不要硬判 `✓`；用 `○ E1`，并在 `notes` 写原因。

### 第 4 步：填 7 列

- `verdict`、`reason_code`、`category` 必须配套。
- `one_liner` 写人话，不要写代码。
- `evidence_quote` 必须逐字复制；不要改写、翻译、加省略号。
- `confidence_1_5`：5 = 很确定，3 = 有边界，1 = 基本靠猜。

### 第 5 步：保存

- 另存为 **CSV UTF-8（逗号分隔）**。
- 不要改列名、不要删列、不要改 `openalex_id`。
- 40 行都要有 `verdict`；可以分批填，但最终要填完。

### 第 6 步：评分

见第 9 节。

---

## 4. 符号总表

### 4.1 判定

| 符号 | 含义 | 计数 |
|---|---|---|
| `✓` | 纳入：主题、对象、方法、条件、指标都符合，且 DOI 核验 pass | primary 计入 K；review/background 计入 B；preprint 计入 P |
| `×` | 排除：明确不符合 | 计入 X |
| `○` | 待核：无法确认，不是“排除” | 计入 O，**不计入 K** |

注意：

- `✓` 只代表“符合题目 + DOI 核验通过”，**不代表内容优质**。
- `○` 不是“坏文献”，是“这轮无法确认”；不要把它写成 `×`。
- `×` 必须带理由码；`✓` 的理由码留空。

### 4.2 排除码（`×` 用）

| 代码 | 含义 | 典型证据 | 例子 |
|---|---|---|---|
| `R1` | 已撤稿 | 撤稿声明/Crossref update-to | 期刊标注 Retracted |
| `P1` | 类型不符 | OpenAlex `type` | paratext、erratum、book review、conference abstract |
| `Y1` | 年份越界 | `year` 早于窗口 | 2021–2026 窗口里的 2019 年论文 |
| `L1` | 语言不符 | `language` 不在范围 | 只要英文，出现西班牙语 |
| `V1` | 版本重复 | 预印本与已发表同时命中 | arXiv 版 + 期刊版 |
| `T1` | 主题不符 | 标题/摘要 | 钙钛矿用于光解水、光电探测器 |
| `S1` | 体系/对象不符 | 材料/器件/样本不同 | 钙钛矿忆阻器 vs 太阳能电池 |
| `M1` | 手段/方法不符 | 方法段 | 表面掺杂、缺陷工程、载流子管理、测复合速度 |
| `C1` | 条件/情境不符 | 条件段 | 温度/浓度/规模/地区/政策情境不同 |
| `I1` | 指标/结果不符 | 结果段 | 效率/稳定性/精度/变量口径不同 |

### 4.3 待核码（`○` 用）

| 代码 | 含义 | 处理 |
|---|---|---|
| `D1` | 无 DOI | 主题相关但无 DOI；先别引用 |
| `D2` | DOI 无法解析 | Crossref/DataCite 都查不到 |
| `D3` | 标题不一致 | DOI 指向的标题对不上，或 CJK/译名无法比对 |
| `D4` | 核验服务不可用 | 本轮 Crossref/DataCite 无响应 |
| `E1` | 证据不足 | 摘要缺失、evidence 为空、没提到关键信息 |

### 4.4 类别（`category`）

| 类别 | 含义 | 计数 |
|---|---|---|
| `primary` | 原始研究 | ✓ 时计入 K |
| `review` | 综述 | ✓ 时计入 B，不占 K |
| `background` | 背景/奠基/观点候选 | ✓ 时计入 B，不占 K |
| `preprint` | 预印本 | ✓ 时计入 P，不占 K；默认不进正式参考文献 |

- 综述、Perspective、Preview、评论：不要填 `primary`。
- `review` 和 `background` 都不占 K；不确定时，标题有 Review 用 `review`，Perspective/Preview/观点用 `background`。
- 综述/观点只有在**主题相关**时才 `✓ B`；如果它明显是另一个主题的综述，仍按 `T1/S1` 排除。
- `background_candidate=true` 的记录按 `review/background` 处理，**不受 Y1 限制**；主题不符仍用 `T1/S1`。

### 4.5 其他列

| 列 | 怎么填 |
|---|---|
| `one_liner` | 非空，≤24 字；`✓` 写纳入理由，`×` 写排除理由，`○` 写待核原因 |
| `evidence_quote` | 逐字复制 evidence/title；`✓` 和语义 `×` 必填；`○ E1` 可空 |
| `confidence_1_5` | 1–5；3 以下请在 notes 写原因 |
| `notes` | 可选；记录边界、犹豫、需要读全文的点 |

---

## 5. 判定顺序（first-fail）

```
R1 → P1 → Y1 → L1 → V1 → T1 → S1 → M1 → C1 → I1 → D1 → D2/D3/D4 → E1
```

含义：

1. 先看元数据：撤稿、类型、年份、语言、版本。
2. 再看语义：主题 → 体系/对象 → 手段/方法 → 条件/情境 → 指标/结果。
3. 最后看 DOI/核验/证据。
4. 只记**第一个**不通过的原因，不要一篇文章写多个理由码。

重要：

- **无 DOI 但主题明显不符**：先判 `T1/S1/M1`，不要直接 `D1`。
- **摘要为空**：主题可由标题判；对象/方法/条件/指标一律 `E1`。
- **综述/观点**：`category` 用 `review` 或 `background`，`verdict` 可以是 `✓`，但不计入 K。

---

## 6. 边界与例子

| 情况 | 判 | 说明 |
|---|---|---|
| 钙钛矿用于光解水/光电探测器 | `T1` | 应用主题不同 |
| 钙钛矿忆阻器 | `S1` | 器件/对象不同 |
| 表面掺杂、缺陷工程、载流子管理 | `M1` | 同一对象，手段不同 |
| 测 GB 复合速度，不是钝化 | `M1` | 研究手段不同 |
| 温度/浓度/规模不同 | `C1` | 条件不同 |
| 效率 vs 稳定性 vs 精度 | `I1` | 指标不同 |
| 综述/观点/Preview | `✓ B` | `category=review/background`，不计 K |
| 摘要为空、标题能判主题 | `○ E1` | 对象/方法无证据，不硬判 ✓ |
| 主题相关但无 DOI | `○ D1` | 不是排除 |
| 无 DOI 且主题不符 | `× T1/S1/M1` | first-fail 先语义 |
| 预印本与已发表版本同时出现 | `× V1` | 保留已发表版 |
| DOI 指向的标题对不上 | `○ D3` | 不直接判 × |
| 书评/会议前言/paratext | `× P1` | 类型不符 |

### 三个最容易错的

1. **把综述当 primary**  
   综述可以 ✓，但必须是 `review/background`，不计 K。

2. **把无 DOI 当排除**  
   无 DOI 是 `○ D1`，不是 `×`；除非主题/方法也不符。

3. **凭空补 evidence_quote**  
   引文必须逐字在 evidence/title 里；不能改写、翻译、总结。

---

## 7. 每条怎么填（模板）

```text
verdict: ✓ / × / ○
reason_code: （✓ 留空；× 填排除码；○ 填待核码）
category: primary / review / background / preprint
one_liner: ≤24 字
evidence_quote: "从 evidence/title 复制的逐字原文"
confidence_1_5: 1–5
notes: 可选
```

### 示例（generic，不对应具体行）

| 情况 | verdict | code | category | one_liner | quote |
|---|---|---|---|---|---|
| 界面钝化原始研究 | ✓ | 空 | primary | 界面钝化，直接相关 | 摘要中的钝化句 |
| 表面掺杂 | × | M1 | primary | 表面掺杂，非钝化 | 摘要中的掺杂句 |
| 光解水 | × | T1 | primary | 水分解应用，非钝化 | 标题/摘要句 |
| 综述 | ✓ | 空 | review | 综述，作背景 | 摘要/标题句 |
| 空摘要 | ○ | E1 | primary | 摘要缺失，待读全文 | 可空 |
| 主题相关无 DOI | ○ | D1 | primary | 无 DOI，先别引用 | 可空 |

---

## 8. 常见错误

| 错误 | 后果 | 正确做法 |
|---|---|---|
| 综述填 `primary` | K 虚高 | `review/background` |
| 无 DOI 直接 `× D1` | 把相关文献排掉 | 主题相关用 `○ D1`；主题不符先 `T1/S1/M1` |
| `evidence_quote` 改写/翻译 | audit 拒绝 | 逐字复制 |
| `one_liner` 超过 24 字 | audit 拒绝 | 压缩到 24 字内 |
| 一篇文章写多个理由码 | 计数不闭合 | first-fail 只写一个 |
| 只看标题不看 evidence | 对象/方法误判 | 读 evidence；没有就 `E1` |
| 只标有把握的条目 | 覆盖率不足 | 40 条全填；不确定用 `○ E1` + notes |
| 先看模型标签再标 | 盲标失效 | 标完再看/再评分 |

---

## 9. 标完怎么算

### 人-模型一致率

```bash
python tests/score_annotation.py \
  --labels tests/annotation/annotation_packet.csv \
  --reference tests/gold/seed_labels.json
```

输出：

- verdict/reason/category 一致率
- verdict/reason 的 Cohen's κ
- 不一致条目
- 未填/未匹配数量

注意：这里的 reference 是开发期 seed，不是第二个人工标注；结果是**人-模型一致率**，不是人-人一致率。

### 人-人一致率

找第二位同学独立标同一份，另存为 `personB.csv`：

```bash
python tests/score_annotation.py --labels personA.csv --reference personB.csv
```

这才是验收要的人-人 κ。

---

## 10. 验收线

| 指标 | 目标 |
|---|---|
| verdict 一致率 | ≥0.80 |
| verdict Cohen's κ | ≥0.60 |
| 三次重复漂移 | ≤10% |
| `evidence_quote` 覆盖率 | 100%（✓ 和语义 ×） |

当前模型对 seed 的盲评结果（materials 28 条）：

- verdict 0.857–0.929
- exact triple 0.679–0.750
- drift 7.1–10.7%

所以目前仍是 beta，不是 v1.0。人工标注是为了确认真实水平，不是为了把数字做漂亮。

---

## 11. 时间与节奏

- 40 条约 90–120 分钟。
- 建议分 3 次，每次 13–14 条，按 topic 分开。
- 先标 10 条试手，确认格式；再标剩下 30 条。
- 每 20–30 分钟休息一次，避免“看什么都像相关”的疲劳。

---

## 12. 盲标与隐私

- 标注期间不要打开 `tests/gold`、`runs/*.semantic*`、`tests/make_semantic_*`。
- 不要和模型讨论具体某条该判什么；可以问“这个理由码是什么意思”。
- 文献标题/摘要本身是公开元数据；不要提交 `.env` 或 API key。
- 标注 CSV 可以留在本地；如果要提交到仓库，先确认没有敏感信息。

---

## 13. 用另一个模型做第二标注

可以，但要知道它证明什么：

- **能证明**：两个模型在同一批文献上是否稳定、是否共享同一种偏差。
- **不能证明**：模型判断正确；也不能替代人-人 κ。
- 结论只能写成“模型-模型一致率”，不能写成“人工验证通过”。

做法：

1. 把 `tests/annotation/annotation_packet.json` 和本说明书发给另一个模型。
2. 使用 `tests/annotation/MODEL_PROMPT_V3.md` 里的提示词。
3. 要求它不要读 `tests/gold`、`runs/*.semantic*`。
4. 输出 `runs/modelB.semantic.json`，覆盖 40 条。
5. 评分：

```bash
# 模型-模型
python tests/score_annotation.py --labels runs/modelA.semantic.json --reference runs/modelB.semantic.json

# 模型-人工
python tests/score_annotation.py --labels runs/modelB.semantic.json --reference personA.csv

# 模型-开发 seed（只作趋势）
python tests/score_annotation.py --labels runs/modelB.semantic.json --reference tests/gold/seed_labels.json
```

注意：

- 两个模型最好来自不同厂商/实验室；同家族一致性会偏高。
- 模型可能更“乐观”，重点看 `E1`、`S1/M1`、`B` 的差异。
- 模型的 `confidence` 不是校准概率，只作参考。
- 输出过不了 `evidence_quote` 校验，先修格式，不要直接算一致率。

---

## 附录 A：标完后的快速检查清单

- [ ] 40 行都有 `verdict`
- [ ] 每个 `×` 都有合法 `reason_code`
- [ ] 每个 `○` 都有合法 `reason_code`
- [ ] 每个 `✓` 的 `reason_code` 为空
- [ ] `category` 都是 `primary/review/background/preprint`
- [ ] `one_liner` 非空且 ≤24 字
- [ ] `✓` 和语义 `×` 都有逐字 `evidence_quote`
- [ ] `confidence_1_5` 都是 1–5
- [ ] 保存为 CSV UTF-8，列名未改
- [ ] 已跑 `score_annotation.py`

---

## 附录 B：CSV 列说明

| 列 | 只读/填写 | 说明 |
|---|---|---|
| `record_id` | 只读 | 盲标编号，如 M-04 |
| `topic` | 只读 | 题目 |
| `openalex_id` | 只读 | 回查用 |
| `title` | 只读 | 原文标题 |
| `year` | 只读 | 年份 |
| `type` | 只读 | OpenAlex type |
| `background_candidate` | 只读 | true = 综述/观点/背景候选；按 review/background，不受 Y1 |
| `doi` | 只读 | DOI，可能为空 |
| `evidence` | 只读 | 摘要片段，可能为空 |
| `evidence_field` | 只读 | abstract/title |
| `year_ok` | 只读 | 年份是否在窗口 |
| `type_ok` | 只读 | 类型是否接受 |
| `language_ok` | 只读 | 语言是否在范围 |
| `retracted_ok` | 只读 | 是否非撤稿 |
| `version_ok` | 只读 | 是否非版本重复 |
| `verification_status` | 只读 | pass/fail/unavailable |
| `verification_reason` | 只读 | no_doi/title_mismatch 等 |
| `verdict` | 填写 | ✓/×/○ |
| `reason_code` | 填写 | 见第 4 节 |
| `category` | 填写 | primary/review/background/preprint |
| `one_liner` | 填写 | ≤24 字 |
| `evidence_quote` | 填写 | 逐字引文 |
| `confidence_1_5` | 填写 | 1–5 |
| `notes` | 填写 | 可选 |
