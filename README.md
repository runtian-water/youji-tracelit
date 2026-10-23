# 有迹（TraceLit）

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)
![Status: beta](https://img.shields.io/badge/status-beta-orange)

面向本科大创与科研训练的可审计文献筛选 Skill。检索 OpenAlex、核验 DOI，输出排除审计表、复现记录、GB/T 7714 参考文献与成本。

不写综述，不判定创新性，不提供全文。

**状态：beta / research prototype。** 语义判定要求 `evidence_quote` 逐字校验，但仍需人工复核；`tests/gold/seed_labels.json` 是回归集，不是独立验证。示例报告见 `examples/`。MIT License。

## 仓库结构

```text
.
├── SKILL.md                  # Skill 入口：铁律、流程、输出契约
├── scripts/main.py           # search / verify / audit / docx / doctor
├── references/               # API 契约、理由码、GB/T 7714、学科窗口、输出模板
├── docs/                     # 操作卡、验收标准、盲评结果、盲标说明书、发布说明
├── examples/                 # 三份示例报告 + 对应的语义判定 JSON
├── tests/                    # 42 项单测、seed gold、40 条盲标包、盲评输入
└── .github/workflows/ci.yml  # Python 3.10 / 3.13 单元测试
```

逐文件说明见 [`docs/project-structure.md`](docs/project-structure.md)。

## 文档导航

| 想做什么 | 看哪里 |
|---|---|
| 5 分钟跑通 | [`docs/quickstart.md`](docs/quickstart.md) |
| 人工盲标 40 条 | [`docs/annotation-manual.md`](docs/annotation-manual.md)（可打印 [`docs/annotation-manual.docx`](docs/annotation-manual.docx)） |
| 了解质量边界 | [`docs/acceptance.md`](docs/acceptance.md)、[`docs/blind-results.md`](docs/blind-results.md) |
| 查看模型 B 标注复核 | [`docs/modelB-results.md`](docs/modelB-results.md) |
| 上传 GitHub / 发 Release | [`docs/publishing.md`](docs/publishing.md) |
| 参与开发 | [`CONTRIBUTING.md`](CONTRIBUTING.md) |

## 能查 / 不能查

| 范围 | 状态 |
|---|---|
| 英文期刊/会议/预印本 | ✓ |
| 中文核心期刊 | △ OpenAlex 覆盖有限，需 CNKI/万方补充 |
| 专利/标准 | ✗ 请用 Google Patents / CNIPA |
| 全文可读性 | ✗ 只给 DOI/元数据 |
| 系统综述/元分析 | ✗ 非穷尽检索 |
| “证明没人做过” | ✗ 只给缺口候选，必须读引言 |

## 安装

1. 目录名保持 `tracelit`（与 `SKILL.md` 的 `name` 一致）。
2. 放入你的 agent 的 skills 目录，例如 `~/.claude/skills/tracelit`。GitHub 仓库可以叫 `youji-tracelit`，安装时目录名用 `tracelit`。
3. 要求 Python 3.10+。核心零依赖；`rapidfuzz`、`certifi` 可选。

## 配置 OpenAlex key

- 免费申请：<https://openalex.org/settings/api>，无需信用卡。
- 免费额度：`$1/天 ≈ 10000 credits`；`search` 10 credits/次，`filter` 1 credit/次。
- 寻迹约 10 credits；循迹默认 20（主检索+背景）；溯迹约 20 + 3–5 个 facet。无 key 约够 50 次循迹。
- 超额请求会被拒绝，不会自动扣费。
- 校园网通常是共享出口 IP；无 key 的 `$0.10/天` 会被多人跑光，正式检索请配 key。A4 操作卡见 `docs/quickstart.md`。

Linux/macOS：

```bash
export OPENALEX_API_KEY="your-key"
```

Windows PowerShell：

```powershell
$env:OPENALEX_API_KEY="your-key"
```

也可以把 key 写进项目根目录的 `.env`（一行 `OPENALEX_API_KEY=...`），`.gitignore` 已忽略该文件。

不要把 key 写进仓库、输出或日志。检查：

```bash
python scripts/main.py doctor --tier 循迹
```

## 使用

```bash
# 1. 检索（寻迹可无 key；循迹/溯迹需要 key）
python scripts/main.py search \
  --query "perovskite passivation" \
  --search '(perovskite OR "halide perovskite") AND ("interface passivation" OR passivation)' \
  --field materials \
  --to-year 2026 \
  --tier 循迹 \
  --out runs/search.json

# 先看检索式与预估成本，不发请求
python scripts/main.py search --query "..." --tier 循迹 --dry-run

# --field 决定默认窗口（cs 3 / materials 5 / math 10 / social 10）
# --from-year 可显式覆盖；不传 --field 时按题目关键词推断
# --history 仅用于 Y1 审计；默认关闭，避免老论文挤占样本
# --background 默认随循迹/溯迹开启（+10 credits）；--foundational 可选（+10 credits）
# 溯迹：--tier 溯迹 --facet "label=expr"（3–5 个，各 +10 credits；不传用默认 facet）

# 2. Crossref → DataCite 核验
python scripts/main.py verify --input runs/search.json --out runs/verified.json

# 3. 生成判定模板（mode=semantic），交给 LLM 填 verdict/reason_code/category/one_liner
python scripts/main.py audit --input runs/verified.json --template > runs/judgments.json

# 4. 校验计数与理由码
python scripts/main.py audit \
  --input runs/verified.json \
  --judgments runs/judgments.json \
  --format md \
  --basis "未命中特定信号，取安全超集"
```

### 一条命令

```bash
python scripts/main.py run \
  --query "perovskite passivation" \
  --search '(perovskite OR "halide perovskite") AND ("interface passivation" OR passivation)' \
  --field materials --tier 循迹 --out-dir runs/my-topic

# 填 runs/my-topic/judgments.template.json → judgments.json（mode=semantic）
python scripts/main.py audit --input runs/my-topic/verified.json \
  --judgments runs/my-topic/judgments.json --format md --out runs/my-topic/report.md
python scripts/main.py docx --input runs/my-topic/report.md --out runs/my-topic/report.docx
```

`run` 做 search + verify + 模板；`--judgments` 可直接接 audit；`--docx` 需与 `--judgments` 同用。docx 是 A4 页面，表格为 8 列审计表。

`audit` 会校验 `X+O+K+B+P=M`、`✓` 是否都有 DOI pass、`K≥3`，并给出 `K<3` 警告；`--format md` 会直接渲染首行的档位/依据/学科/时间/语言/key、图例、8 列表格、复现块、GB/T 7714 参考文献（背景/预印本分节）与固定尾注。`zh`/`en|zh` 模式会加 CNKI/万方覆盖提示。参数槽位行（对象/手段/条件/指标）由 LLM 按题目补。stdout 只出报告，校验 JSON 写 stderr；`--out` 只写报告。

`judgments.json` 的 `mode` 必须是 `semantic`（`audit --template` 已带上）；缺失或非法会被 md 门禁拒绝。`✓` 和语义 `×` 必须带 `evidence_quote`，audit 会校验它是 `evidence`/`title` 的逐字子串。`tests/make_judgments.py` 只是机械 smoke test，不代表语义判定。它的输出带 `mode=mechanical_smoke`；`audit --format md` 默认拒绝渲染，必须加 `--allow-smoke`，且首行会打 `[机械冒烟·非语义判定]`。

## 测试

```bash
python -m unittest discover -s tests -v
python tests/eval_gold.py --run materials --judgments examples/judgments/materials.semantic.json
```

`tests/gold/seed_labels.json` 是开发期回归集，不是独立验证；`eval_gold.py` 默认只做趋势记录、不设硬门禁（需要失败退出码时加 `--strict`）。发布质量结论前需替换为独立人工标注。盲评与漂移结果见 `docs/blind-results.md`：当前 verdict 0.857–0.929，exact triple 0.679–0.750，仍未达 v1.0。另一个模型标了 40 条：早期 B/B2 vs seed verdict 0.875、κ≈0.81；修正 packet 后 B3 vs seed verdict 0.95、κ 0.92，仅剩 2 条 B/T1 边界争议。见 `docs/modelB-results.md`。这仍是模型-模型/模型-seed，不是人工验证。

40 条人工盲标包：`tests/annotation/annotation_packet.csv`（14 materials + 13 social + 13 chinese，不含标签）。完整说明书：[`docs/annotation-manual.md`](docs/annotation-manual.md)（可打印版 [`docs/annotation-manual.docx`](docs/annotation-manual.docx)）；简版：`tests/annotation/ANNOTATION_GUIDE.md`。评分：

```bash
python tests/score_annotation.py --labels tests/annotation/annotation_packet.csv --reference tests/gold/seed_labels.json
```

两位人工标注时，把 `--reference` 换成第二份 CSV，算人-人 κ。  
用另一个模型做第二标注：见 `tests/annotation/MODEL_PROMPT_V3.md`；结果只能称模型-模型一致率。

## 边界

- 非穷尽检索，不等同于系统综述；结论只适用于本次检索样本。
- 不提供全文，也不判断机构权限。
- 专利与标准不在 OpenAlex 覆盖范围，请用 Google Patents / CNIPA 另查。
- OpenAlex 元数据可能有误；`✓` 只代表 DOI 与标题/年份核验通过，不代表内容优质。
- 负结果少发表，低命中不等于空白。
