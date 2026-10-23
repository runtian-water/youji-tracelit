# 仓库结构

版本：`0.5.0-beta.1`。本文件说明每个目录和文件的作用，以及新增文件应该放在哪里。

## 总览

```text
.
├── SKILL.md                         # Skill 入口（根目录，name: tracelit）
├── README.md                        # 项目总览与命令参考
├── LICENSE                          # MIT
├── CHANGELOG.md                     # 版本变更
├── CITATION.cff                     # GitHub “Cite this repository”
├── CONTRIBUTING.md                  # 开发与 PR 规则
├── SECURITY.md                      # 密钥与漏洞报告
├── requirements-optional.txt        # rapidfuzz / certifi（可选）
├── .env.example                     # key 占位符，不含真实 key
├── .gitignore                       # 忽略 .env、runs/、缓存等
├── .editorconfig
├── .github/
│   └── workflows/
│       └── ci.yml                   # Python 3.10 / 3.13 单测
├── scripts/
│   └── main.py                      # search / verify / audit / docx / doctor
├── references/
│   ├── README.md
│   ├── api-contract.md              # OpenAlex/Crossref 字段与白名单
│   ├── reason-codes.md              # 封闭理由码 R1…I1, D1…D4, E1
│   ├── gbt7714.md                   # GB/T 7714 著录规则
│   ├── disciplines.md               # 学科识别与默认时间窗
│   └── output-templates.md          # 报告/表格/复现块模板
├── docs/
│   ├── README.md                    # 文档索引
│   ├── quickstart.md                # A4 操作卡
│   ├── acceptance.md                # v1.0 验收标准
│   ├── blind-results.md             # 三次盲评结果
│   ├── modelB-results.md            # 模型 B/B2/B3 复核
│   ├── annotation-manual.md         # 40 条盲标说明书
│   ├── annotation-manual.docx       # 同上，A4 Word
│   ├── project-structure.md         # 本文件
│   ├── publishing.md                # GitHub 上传与 Release
│   ├── release-notes-v0.5.0-beta.1.md
│   └── handoff-2026-10-22.md        # 开发交接
├── examples/
│   ├── README.md
│   ├── materials.semantic.report.md # 示例报告（8 列审计表/复现块/GB/T）
│   ├── social.semantic.report.md
│   ├── chinese.semantic.report.md
│   └── judgments/
│       ├── README.md
│       ├── materials.semantic.json  # 与示例报告对应的判定
│       ├── social.semantic.json
│       ├── chinese.semantic.json
│       ├── modelB.semantic.json     # 模型 B 的三次复核结果
│       ├── modelB2.semantic.json
│       └── modelB3.semantic.json    # 修正 packet 后的最新版
└── tests/
    ├── README.md                    # 测试资产说明
    ├── test_core.py                 # 42 项单测，离线
    ├── cases.md                     # 手工验收案例
    ├── eval_gold.py                 # 对 seed gold 的趋势回归
    ├── score_annotation.py          # 盲标 CSV/JSON 评分（一致率/κ）
    ├── make_judgments.py            # 机械冒烟 judgments（非语义）
    ├── make_semantic_materials.py   # 开发期 seed 生成脚本
    ├── make_semantic_social.py
    ├── make_semantic_chinese.py
    ├── gold/
    │   ├── README.md
    │   └── seed_labels.json         # 84 条开发期回归标签
    ├── annotation/
    │   ├── annotation_packet.csv    # 40 条盲标空表（人工填 7 列）
    │   ├── annotation_packet.json   # 同一批的模型输入
    │   ├── annotation_verified.json
    │   ├── ANNOTATION_GUIDE.md
    │   ├── MODEL_ANNOTATION_PROMPT.md
    │   ├── MODEL_PROMPT_V2.md
    │   └── MODEL_PROMPT_V3.md
    ├── blind/
    │   ├── PROMPT.md                # 盲评提示词
    │   └── materials_input.json     # 28 条盲评输入（无标签）
    └── fixtures/
        ├── one.json                 # 最小检索结果
        ├── one.verified.json
        ├── one.judgments.json
        ├── one.audit.md
        └── real_meta.verified.json
```

## 分类原则

| 类型 | 位置 | 判据 |
|---|---|---|
| 代码 | `scripts/`、`tests/*.py` | 会被执行；`scripts/main.py` 保持单文件 |
| 契约/规范 | `references/` | 模型或维护者需要逐条遵守的规则 |
| 面向人的说明 | `docs/` | 操作、验收、研究结果、发布流程 |
| 可公开的样例 | `examples/` | 已脱敏、体积小、能直接看懂输出格式 |
| 测试资产 | `tests/` | 单测、fixtures、回归标签、盲标包 |
| 仓库配置 | 根目录、`.github/` | 只与 GitHub/CI/编辑器有关 |

## 刻意不放进仓库

| 内容 | 原因 |
|---|---|
| `.env` | 含真实 `OPENALEX_API_KEY` |
| `runs/` | 本地检索临时产物；只把挑选后的判定 JSON 放进 `examples/judgments/` |
| `__pycache__/`、`*.pyc` | 生成物 |
| `release/` 与四个 zip | 第一次上传不需要；Release 附件单独生成，见 `docs/publishing.md` |
| `说明书.docx` 之外未脱敏的标注 | 避免把个人标注草稿当成交付物 |

## 新增文件的放置规则

1. 新命令/行为 → 改 `scripts/main.py`，在 `README.md` 与 `SKILL.md` 同步参数说明，并在 `tests/test_core.py` 补用例。
2. 新理由码或判定边界 → `references/reason-codes.md` + `SKILL.md` + 测试 + `CHANGELOG.md`。
3. 新的用户文档 → `docs/`，并在 `docs/README.md` 加一行。
4. 新的示例输出 → `examples/`；如果含判定 JSON，放 `examples/judgments/` 并更新其 README。
5. 新的评估集 → `tests/gold/` 或 `tests/annotation/`，必须注明是人工、模型还是开发期 seed。
6. 生成物、密钥、本地运行结果 → 不提交；先更新 `.gitignore`。

## 文件命名

- 目录和文件名用小写英文与连字符，避免空格；中文标题写在文件内容里。
- 测试/评估产物用 `<topic>.<kind>.json`，例如 `materials.semantic.json`。
- 版本相关文档带版本号，例如 `release-notes-v0.5.0-beta.1.md`。
