# 贡献指南

TraceLit 目前是 **beta / research prototype**。欢迎修 bug、补测试、改文档、补边界案例；涉及语义判定口径的改动请先开 issue 说明理由。

## 环境

- Python 3.10+。
- 核心零依赖；`requirements-optional.txt` 里的 `rapidfuzz`、`certifi` 只用于加速和 TLS。
- 不需要 OpenAlex key 就能跑单元测试。

```bash
cp .env.example .env      # 只有跑真实检索时才需要填 OPENALEX_API_KEY
python -m unittest discover -s tests -v
```

## 目录约定

| 目录 | 放什么 |
|---|---|
| `SKILL.md` | Skill 入口和行为铁律；不要在这里写实现细节 |
| `scripts/main.py` | 全部命令行实现，保持单文件、标准库优先 |
| `references/` | 对 LLM/维护者可见的契约：理由码、API 字段、GB/T 格式、学科窗口、输出模板 |
| `docs/` | 面向使用者和维护者的说明；不要放会被代码读取的数据 |
| `examples/` | 已脱敏的示例报告与判定 JSON；不放 `runs/` 原始产物 |
| `tests/` | 单测、回归集、盲标包、盲评输入；见 `tests/README.md` |

新增文件前先看 [`docs/project-structure.md`](docs/project-structure.md)。

## 修改规则

1. **理由码封闭**：排除理由只能来自 `references/reason-codes.md`。新增理由码时，同一次改动里要更新码表、`SKILL.md` 的判定顺序、相关测试和 `CHANGELOG.md`。
2. **引文门禁**：`✓` 与语义 `×` 必须带 `evidence_quote`，且必须是 `evidence`/`title` 的逐字子串。不要为了过校验而改写原文。
3. **模式白名单**：`judgments.json` 的 `mode` 只能是 `semantic` 或 `mechanical_smoke`；后者不能用于质量结论。
4. **计数不变量**：`X+O+K+B+P=M`；`K≥3`（盲标包等分层样本除外，需注明）；所有 `✓` 必须 DOI pass。
5. **零虚构**：不要用记忆补文献、标题、作者或 DOI；网络失败时输出失败状态。
6. **不要提交密钥或本地产物**：`.env`、`runs/`、`__pycache__/` 已被忽略；提交前跑 `git status` 再确认。
7. **测试**：改 `scripts/main.py` 或 `references/` 后必须跑完整单测；改判定规则时补一个最小复现用例。

```bash
python -m unittest discover -s tests -v
python tests/eval_gold.py --run materials \
  --judgments examples/judgments/materials.semantic.json
```

`eval_gold.py` 默认只记录趋势、不以非零码退出；发布前评估可加 `--strict`。

## 提交 PR

- 一个 PR 只做一件事；说明动机、行为变化和验证方式。
- 涉及输出格式的改动，附一份改动前后的报告片段。
- 涉及语义标签的改动，明确说明是**人工标注**、**模型标注**还是**开发期 seed**，不要把模型-模型一致率写成人工验证。
- CI 会在 Python 3.10 和 3.13 上跑单测。
- Commit message 用祈使句，例如 `fix: reject non-verbatim evidence quotes`。

## 人工盲标

如果你要参与 40 条盲标，请先读 [`docs/annotation-manual.md`](docs/annotation-manual.md) 或简版 [`tests/annotation/ANNOTATION_GUIDE.md`](tests/annotation/ANNOTATION_GUIDE.md)。标注期间不要看 `tests/gold/seed_labels.json`、`examples/judgments/`、`runs/*.semantic*` 和 `tests/make_semantic_*`。

## 许可证

提交即表示你同意以 MIT License 贡献代码和文档。
