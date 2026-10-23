# v1.0 验收标准

当前状态：**beta / research prototype**。以下门槛未全部满足前，不对外宣称 v1.0 或“可审计语义筛选”。

## 必须满足

1. **无标签准确率 ≥ 0.80**
   - 不给模型看标签，只给 title/evidence，让它自产 judgments。
   - 与独立人工标签比 verdict/reason/category。
2. **三次重复漂移 ≤ 10%**
   - 同一批 28 条，独立跑 3 次；逐条 verdict/reason 一致率 ≥90%。
3. **人-模型一致率 κ ≥ 0.60**
   - 1–2 名人工盲标 40 条；人-人先算一致率，低则先修 S1/M1/C1 边界。
4. **evidence_quote 覆盖**
   - 所有 `✓` 和语义 `×` 都有逐字引文，且在 `evidence`/`title` 中。
5. **结构不变量**
   - `X+O+K+B+P=M`；`K≥3`；`✓` 全部 DOI pass。
6. **失败模式**
   - 断网、0 命中、429、Crossref 全挂、无 key 都有明确输出，不用记忆补。
7. **成本**
   - `credits`/`elapsed` 可见；预算耗尽不重试；无 key 的校园 NAT 场景有提示。

## 当前证据

- 42 项单测通过。
- seed gold 回归 28/28 × 3 组；但 seed 是开发期标签，不是独立验证。
- 三份语义报告：materials K10/B10/X7/O1，social K17/B3/X3/O5，chinese K18/B3/X6/O1。
- 盲评已完成 3 次（materials 28 条）：verdict 0.857–0.929，exact triple 0.679–0.750；三次 exact drift 7.1–10.7%。详见 `docs/blind-results.md`。
- 另一个模型（修正 packet 后）vs seed：verdict 0.95、κ 0.92；这是模型-seed，不是人工验证。
- 结论：尚未达到 v1.0；exact triple <0.80，且一对 drift 略高于 10%，人工 κ 未测。下一步先修 M1/T1/S1 边界，再做独立人工标注。

## 不达标时先修什么

- 大量 `E1`：先检查 evidence 600/1200 字是否够判条件/指标。
- 人-人一致率低：先补 S1/M1/C1 的定义和边界例子。
- 漂移高：固定 evidence 截取、降低温度、减少自由文本。
- 准确率低：先查检索式是否过窄，再查模型。
