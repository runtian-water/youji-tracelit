# 有迹（TraceLit）A4 操作卡

## 0. 安装与 key

```bash
# 目录名保持 tracelit，放入 agent 的 skills 目录
# 免费 key：https://openalex.org/settings/api（无需信用卡，$1/天）
cp .env.example .env
# 编辑 .env，填入 OPENALEX_API_KEY
python scripts/main.py doctor --tier 循迹
```

校园网通常是共享出口 IP；无 key 的 `$0.10/天` 会被多人一起用光，正式检索请配 key。`.env` 已在 `.gitignore` 中。

## 1. 一条命令检索

```bash
python scripts/main.py run \
  --query "你的题目" \
  --search "(核心概念 OR 同义词) AND (对象 OR 方法)" \
  --field materials \
  --tier 循迹 \
  --out-dir runs/my-topic
```

产物：

```
runs/my-topic/search.json             主检索 + 背景
runs/my-topic/verified.json           DOI 核验
runs/my-topic/judgments.template.json 待填语义判定
```

`--field`：`cs|materials|math|social|unknown`。  
`--tier`：寻迹（快）｜循迹（默认）｜溯迹（加 facet/Top5/缺口）。

## 2. 填语义判定

把 `judgments.template.json` 复制为 `judgments.json`，逐条填：

- `mode`: `semantic`
- `verdict`: `✓` / `×` / `○`
- `reason_code`: `T1/S1/M1/C1/I1` 或 `R1/P1/Y1/L1/V1` 或 `D1/D2/D3/D4/E1`
- `category`: `primary/review/background/preprint`
- `evidence_quote`: `✓` 和语义 `×` 必填，必须是 evidence/title 的逐字子串
- `one_liner`: 非空，≤24 字

## 3. 出报告与 docx

```bash
python scripts/main.py audit \
  --input runs/my-topic/verified.json \
  --judgments runs/my-topic/judgments.json \
  --format md \
  --out runs/my-topic/report.md

python scripts/main.py docx \
  --input runs/my-topic/report.md \
  --out runs/my-topic/report.docx
```

`audit` 的 stdout 只出报告，校验 JSON 在 stderr；`--out` 只写报告。  
docx 是 A4 页面，表格为 8 列审计表。

## 4. 能查 / 不能查

| 范围 | 状态 |
|---|---|
| 英文期刊/会议/预印本 | ✓ |
| 中文核心期刊 | △ OpenAlex 覆盖有限，需 CNKI/万方补充 |
| 专利/标准 | ✗ 请用 Google Patents / CNIPA |
| 全文可读性 | ✗ 只给 DOI/元数据 |
| 系统综述/元分析 | ✗ 非穷尽检索 |
| “证明没人做过” | ✗ 只给缺口候选，必须读引言 |

## 5. 常见错误

- `BudgetError`：当日 credits 用尽；UTC 零点重置，或换 key。
- `AuthError`：key 未激活/错误；重新申请并 `doctor`。
- 大量 `○ D1`：预印本/报告无 DOI；不要当 ✓。
- 大量 `○ E1`：摘要缺失；标题可判主题，对象/方法需读全文。
- `audit` 拒绝渲染：`mode` 不是 `semantic`，或 `evidence_quote` 为空/不在原文。
