# 上传 GitHub 与发版

版本：`v0.5.0-beta.1`（**pre-release**，不是 v1.0）。

本目录（`tracelit-github`）已经是整理好的仓库内容：把它里面的文件放到 GitHub 仓库根目录即可，不需要再解压 zip，也不需要保留外层文件夹。

## 1. 上传前检查

```bash
cd tracelit-github

# 单测必须全绿（42 项）
python -m unittest discover -s tests -v

# 确认密钥、本地产物、缓存都不在待提交列表里
ls -a
find . -name ".env" -o -name "__pycache__" -o -name "*.pyc" -o -path "./runs/*"
```

应当**只有** `.env.example`，没有 `.env`、`runs/`、`__pycache__/`、`release/`。

如果之前初始化过 git，再运行：

```bash
git status --short
```

## 2. 网页上传（最简单）

1. GitHub 新建仓库，例如 `youji-tracelit`。建议：
   - Public；
   - **不要**勾选 “Add a README file / .gitignore / license”，避免和本目录冲突。
2. 打开本目录，把里面**所有内容**（不是 `tracelit-github` 这层文件夹）拖进仓库根目录。
3. Commit message 可用：`TraceLit v0.5.0-beta.1`。
4. 检查仓库首页是否显示 README、`SKILL.md`、`docs/`、`tests/`、`.github/workflows/ci.yml`。

网页上传会漏掉以 `.` 开头的文件（`.github/`、`.gitignore`、`.env.example`、`.editorconfig`）。如果拖拽后这些文件没出现，改用下面的命令行方式。

## 3. 命令行上传（推荐）

在**本目录内**执行：

```bash
cd tracelit-github

git init
git add .
git status --short          # 再确认没有 .env / runs/ / __pycache__
git commit -m "TraceLit v0.5.0-beta.1"

git branch -M main
git remote add origin https://github.com/<你的用户名>/youji-tracelit.git
git push -u origin main

git tag v0.5.0-beta.1
git push origin v0.5.0-beta.1
```

如果使用 SSH，把 remote 换成 `git@github.com:<你的用户名>/youji-tracelit.git`。

## 4. GitHub Release

- Tag：`v0.5.0-beta.1`
- 标题：`TraceLit v0.5.0-beta.1`
- **勾选 “This is a pre-release”**
- 说明：直接复制 [`release-notes-v0.5.0-beta.1.md`](release-notes-v0.5.0-beta.1.md)

Release 附件可选。如需像之前一样提供四个 zip，在仓库**外部**打包，不要把 zip 提交进仓库：

```bash
# 在 tracelit-github 的上一级目录执行
zip -r tracelit-v0.5.0-beta.1.zip tracelit-github \
  -x "tracelit-github/.git/*" "tracelit-github/runs/*" "tracelit-github/.env"
sha256sum tracelit-v0.5.0-beta.1.zip > SHA256SUMS.txt
```

## 5. 上传后验证

在干净目录克隆一次，按新用户流程走：

```bash
git clone https://github.com/<你的用户名>/youji-tracelit.git
cd youji-tracelit

python -m unittest discover -s tests -v
cp .env.example .env          # 填入 OPENALEX_API_KEY
python scripts/main.py doctor --tier 循迹

python scripts/main.py run \
  --query "perovskite passivation" \
  --search '(perovskite OR "halide perovskite") AND passivation' \
  --field materials --tier 寻迹 --dry-run
```

再检查 GitHub 的 **Actions** 页：`tests` workflow 应在 Python 3.10 和 3.13 上通过。

## 6. 安装为 Skill

`SKILL.md` 的 `name` 是 `tracelit`，安装目录名必须也是 `tracelit`：

```bash
# 仓库可以叫 youji-tracelit，安装时目录名用 tracelit
git clone https://github.com/<你的用户名>/youji-tracelit.git ~/.claude/skills/tracelit
```

Windows（PowerShell）：

```powershell
git clone https://github.com/<你的用户名>/youji-tracelit.git "$HOME\.claude\skills\tracelit"
```

## 7. 后续发版

1. 更新 `CHANGELOG.md` 和 `scripts/main.py` 里的 `VERSION`。
2. 在 `docs/` 新增 `release-notes-v<版本>.md`。
3. 跑单测和 `eval_gold.py`。
4. 提交、打 tag、推送 tag，再建 pre-release。
5. 如果语义口径有变化，同步更新 `references/reason-codes.md`、`SKILL.md` 和 `docs/acceptance.md`。

## 8. 不要上传

- `.env`（真实 OpenAlex key）
- `runs/`（本地检索产物）
- `__pycache__/`、`*.pyc`
- `release/` 与本地 zip
- 任何未脱敏的人工标注草稿

`.gitignore` 已覆盖这些路径；`git add .` 后仍建议再看一眼 `git status --short`。
