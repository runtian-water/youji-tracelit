# 契约与规范

这些文件是脚本、Skill 和维护者共同遵守的契约。改这里的规则时，必须同步改 `SKILL.md`、相关测试和 `CHANGELOG.md`。

| 文件 | 管什么 | 什么时候看 |
|---|---|---|
| [`api-contract.md`](api-contract.md) | OpenAlex 请求、字段白名单、脚本与 LLM 之间的输入输出 | 改 `scripts/main.py` 的检索/核验/输出字段时 |
| [`reason-codes.md`](reason-codes.md) | 封闭理由码 `R1/P1/Y1/L1/V1/T1/S1/M1/C1/I1` 与 `D1–D4/E1`；理工/社科双轨含义 | 判定排除理由、补边界案例时 |
| [`gbt7714.md`](gbt7714.md) | GB/T 7714-2015 著录；primary / 背景 / 预印本分节 | 改参考文献渲染时 |
| [`disciplines.md`](disciplines.md) | 理工/社科识别信号与默认时间窗 | 改 `--field` 推断或时间窗时 |
| [`output-templates.md`](output-templates.md) | 首行、8 列审计表、图例、复现块、尾注模板 | 改报告版式时 |

## 优先级

1. `SKILL.md` 的“铁律”优先于本目录的具体格式说明。
2. 本目录优先于 `examples/` 中的历史输出；示例可能来自旧版本。
3. 代码行为与文档冲突时，先补测试复现，再决定改哪一边；不要只改文档掩盖差异。

## 新增理由码的检查清单

- [ ] `reason-codes.md` 增加代码、标签、双轨含义、所需证据和边界例子。
- [ ] `SKILL.md` 的 first-fail 顺序与图例说明同步。
- [ ] `tests/test_core.py` 至少覆盖该码的合法/非法用法（若涉及门禁）。
- [ ] `CHANGELOG.md` 记录行为变化。
- [ ] 检查 `annotation-manual.md` 是否需要更新（人工标注会用到）。
