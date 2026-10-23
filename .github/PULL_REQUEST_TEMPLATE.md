## 改了什么

<!-- 一两句话说明动机和结果 -->

## 类型

- [ ] Bug 修复
- [ ] 新功能 / 新命令
- [ ] 文档
- [ ] 测试 / 评估集
- [ ] 重构（不改变行为）
- [ ] 其他：

## 验证

- [ ] `python -m unittest discover -s tests -v` 通过
- [ ] 涉及回归时运行 `eval_gold.py`（附结果）
- [ ] 涉及输出格式时附改动前后的报告片段
- [ ] 涉及真实检索时说明是否使用 key、credits 消耗

## 检查清单

- [ ] 没有提交 `.env`、`runs/`、`__pycache__/`、`*.pyc`
- [ ] 没有粘贴真实 API key、token 或未脱敏数据
- [ ] 没有把模型-模型 / 模型-seed 一致率写成人工验证
- [ ] 涉及理由码或判定边界时，已同步 `references/reason-codes.md`、`SKILL.md` 和测试
- [ ] 涉及用户可见行为时，已更新 `README.md` 或 `docs/`
- [ ] 需要时已更新 `CHANGELOG.md`

## 备注

<!-- 已知限制、后续工作、需要 reviewer 特别看的地方 -->
