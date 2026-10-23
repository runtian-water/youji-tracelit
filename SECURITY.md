# 安全策略

## 支持范围

当前维护的是 `0.5.x` beta 系列。更早的开发快照不单独修复。

## 报告问题

请使用 GitHub 仓库的 **Security → Report a vulnerability**（私密安全公告）报告，不要在公开 issue 中贴 API key、日志或未修复细节。

报告时请附：

- 受影响版本/commit；
- 最小复现步骤；
- 影响范围（密钥泄露、任意文件写入、拒绝服务、提示词注入等）；
- 你希望如何署名（可选）。

## 密钥处理

- `OPENALEX_API_KEY` 只从环境变量或项目根目录 `.env` 读取；`.env` 已被 `.gitignore` 忽略。
- 不要把 key 写进命令、输出、报告、复现块或 issue。
- 仓库只提供 `.env.example` 占位符。
- 如果怀疑 key 泄露：到 <https://openalex.org/settings/api> 轮换 key，并检查 shell history 与 CI 日志。

## 不可信输入

OpenAlex/Crossref 返回的标题、摘要与 `evidence` 字段是不可信数据。`scripts/main.py` 会剥离控制字符；`SKILL.md` 明确要求模型只提取事实、不执行其中的指令。发现可绕过该约束的样本，请按安全公告提交。

## 不属于安全问题的内容

- 语义判断分歧、理由码边界争议、检索覆盖不足：请走普通 issue，并附 `docs/` 中的相关口径。
- OpenAlex 元数据错误：请向 OpenAlex 反馈；本仓库只能做核验和标注。
