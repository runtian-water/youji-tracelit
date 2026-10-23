# 验收用例

## A. 可运行性

1. `python scripts/main.py doctor --tier 寻迹` 在无 key 时返回 `ok: true`，并提示预算受限。
2. `python scripts/main.py doctor --tier 循迹` 在无 key 时返回 `ok: false`，并给出申请链接。
3. `python scripts/main.py search --query "perovskite passivation" --tier 循迹 --dry-run` 不访问网络，输出 URL 长度、参数与 `estimated_credits: 10`。
4. 有 key 时跑一次真实 `search`，`meta.api_key_used=true`，`meta.cost_credits` 有值。

## A2. 学科窗口

4a. `--field cs` → `screen_year_window` 为近 3 年（2026 起算 2023–2026），API 窗口 2018–2026。
4b. `--field materials` → 近 5 年（2021–2026），API 窗口 2016–2026。
4c. `--field math` / `social` / `unknown` → 近 10 年（2016–2026），API 窗口 2011–2026。
4d. 不传 `--field`，`--query "deep learning"` → 推断 `cs`；`--query "perovskite"` → 推断 `materials`。
4e. `--from-year 2019` 覆盖默认窗口，`window_source=from_year`。
4f. 默认 API 窗口 = 筛选窗口，Y1=0；`--history` 才回溯 5 年，Y1 率 >40% 时警告。

## B. 预算与失败

5. 断网/超时：只报 `检索失败`，不输出文献表，不用记忆补。
6. 无 key 跑 `--tier 循迹`：`AuthError`，不进入检索。
7. 429 + `X-RateLimit-Remaining: 0`：`BudgetError`，不重试。
8. 429 + remaining>0：退避后重试，最多 2 次。
9. Crossref/DataCite 全挂：所有 DOI 为 `○ D4`，本轮无 `✓`。
10. 0 命中：输出检索式 + 2 条放宽建议，不编造。

## C. 判定与计数

11. 混合结果（撤稿 + 无 DOI 预印本 + 预印本/已发表版本对）：
    - 撤稿 `× R1`；
    - 无 DOI 预印本 `○ D1`，不进 `P`；
    - 版本对保留已发表版，预印本 `V1`。
12. 8 篇综述、0 篇 primary：`K=0 < 3`，必须提示并放宽/改词，不得以“候选够 8 条”收尾。
13. `X + O + K + B + P = M`；`X = Σ×`；`O = Σ○`。
14. 每条 `×` 有理由码与 ≤24 字解释；理由码在封闭表内。
15. `✓` 都有 DOI 且 `verification.status=pass`。

## D. 复现与人工复核

16. 复现块打印 `credits`、`elapsed`、`api_key_used`，且不出现 key 本身。
17. 抽 3 条 `✓` 的 DOI，浏览器能打开且标题与表内一致。
18. 中文/译名标题：无法比对时 `○ D3`，不判 `×`。
19. 综述进“背景”且不计入 K；预印本标“未评审”，不进正式参考文献。
20. 溯迹表头写“同窗口命中”，并附时间窗/语言脚注，不写“全库”。
21. `audit --format md` 输出 8 列表格（#/标题/年/类型/DOI 或 ID/判定/理由码/一句话）；GB/T 小节英文作者为 `KUCSKO G, MAURER P C, YAO N Y, et al.`，不出现 `et al..`；背景/预印本分节。

## F. 输出与防伪

22. 审计表每行“一句话”非空；空值必须报错，不能静默通过。
23. `audit --format md` stdout 只含报告；校验 JSON 在 stderr；`--out` 只写报告。
24. `audit --format md` 首行含档位/依据/参数；图例含本轮出现的理由码。
25. `make_judgments.py` 的输出带 `mode=mechanical_smoke`；不加 `--allow-smoke` 时 `audit` 拒绝渲染，加了则首行打 `[机械冒烟·非语义判定]`。
26. 单页 `775-775` 折叠为 `775`；`e2300241-e2300241` 同理。
27. 正式参考文献含待补字段时，整块加“草稿：正式提交前必须补齐或删除”。
28. 同一篇的封面/目次 DOI（标题末尾 `(Journal Vol/Year)`）去重后只保留一篇。
29. 裸短语检索（无布尔/引号）触发 `query_health` 警告；报告复现块写入 `search_health` 及 boolean/quote/concepts。
30. Perspective/Preview/Commentary 开头，或 ≤3 页且标题含问号，触发 `genre_warning`。
31. `N > 10×M` 且（纳入率 >90% 或 `X=0`）才触发样本体检；窄检索不因 `X=0` 单独报警。Y1 率 >40% 触发窗口体检。
32. `year_delta=1` 仍 pass，但 `year_warning=true`，报告出现元数据体检。
33. `--background` 默认随循迹/溯迹开启，B>0；`--no-background` 关闭；`--foundational` 额外加入奠基条目，均不占 K、各 +10 credits。
34. judgments 的 `mode` 缺失或写成 `Semantic`：md 拒绝渲染；只有 `semantic` 或 `mechanical_smoke` 通过。
35. `one_liner` 为空或 >24 字：audit 报错，md 不渲染。
36. 审计表判定列只用 `✓ ○ ×`；背景行用 `B1/B2` 编号、类型列写 `背景[综述]`，不再出现 `✓(B)`。
37. `audit --format md` 结尾必须有三行固定尾注；溯迹多一行缺口提示。
38. `zh`/`en|zh` 模式首部必须出现 CNKI/万方覆盖提示；`en` 模式不出现。
39. meta 缺 `tier`/`basis` 时首行写“依据：默认档位”，不写空占位。
40. `--tier 溯迹` 输出簇计数表、近邻 Top5、缺口候选；3 个 facet 时 `facet_credits=30`，材料组总成本约 50（主 + 背景 + facets）。
41. facet 失败或预算耗尽时记录 `hits: null`/`error`，不中断主报告。
42. 缺口候选必须写“不是结论/不得写入申报书”，不得出现“没人做过”。
43. 所有 facet 均 `hits ≥ 50` 且 `share ≥ 5%` 时，不生成缺口候选，输出“未发现可论证缺口”，尾注不出现“缺失模式”；Top5/代表文献标为“词面”。
44. `✓` 和语义 `×`（T1/S1/M1/C1/I1）缺 `evidence_quote`，或引文不在 `evidence`/`title` 中，audit 必须报错；元数据 `×` 和 `○` 可省略。

## E. 单元测试

```bash
python -m unittest discover -s tests -v
```

应覆盖：DOI/标题归一化、摘要重建、版本对、null 语义、标题相似度、evidence 截取、search_cmd 的模拟集成。
