# 发布清单（RELEASING）

这个文件是给「下一次发版的我」看的。照着从上到下做，不用回忆。

## 0. 一句话状态

- 包名：`memloom`（PyPI 已占用与否发布前先查：<https://pypi.org/project/memloom/>）
- 当前版本：`0.1.0`
- 版本号只有一处真相：`memloom/memloom/__init__.py` 的 `__version__`；
  `pyproject.toml` 里的 `version` 必须同步（两处不一致时以 `__init__` 为准并立刻改 `pyproject`）。

## 1. 发版前必须全绿

```bash
# 1) 测试全绿（不加 -q，失败时看得清）
python -m unittest discover -s tests -t .

# 2) 用真实档案跑一遍，确认三个子命令都能用
python -m memloom doctor
python -m memloom scan

# 3) 全量 + 增量各跑一次，第二次必须是「改动 0 / 复用 N / 新解析 0」
python -m memloom build --out out/release-check --full
python -m memloom build --out out/release-check

# 4) 干跑不写盘
python -m memloom build --dry-run --out out/release-check
```

四条都过才继续。第 3 条是 v0.1 的核心承诺（增量解析），第二次构建只要还有 `本次改动 > 0` 就说明有页面在假变更，先查再发。

## 2. 版本与文档对齐

- [ ] `memloom/__init__.py` 与 `pyproject.toml` 的版本号一致
- [ ] `README.md` 里的测试数量、性能数字与这次实测一致（别抄旧数字）
- [ ] 「已知局限」里没有已经修好的条目（修了就删，别留着自贬）
- [ ] `docs/architecture.md` 的性能段落更新
- [ ] 新增/改动的适配器在 `docs/adapters.md` 里有对应说明和 fixture
- [ ] `CHANGELOG.md` 加一节（见下）

## 3. 提交与打标签

```bash
git add -A
git -c user.name="memloom" -c user.email="memloom@example.com" \
    commit -m "memloom v0.1.0: <一句话>"
git tag -a v0.1.0 -m "memloom v0.1.0"
```

标签用 `vX.Y.Z`，与 `__version__` 一致（少一个 `v` 或写成 `0.1` 都会让 `pip install git+...@v0.1.0` 失败）。

## 4. 推到 GitHub

仓库第一次建：

```bash
# 需要已登录 gh（gh auth status）
gh repo create memloom --public --source=. --remote=origin \
   --description "Turn your AI coding sessions into a navigable Obsidian memory vault."
git branch -M main
git push -u origin main
git push origin v0.1.0
```

已有仓库（后续发版）：

```bash
git push origin main
git push origin v0.1.0
```

仓库设置建议（第一次建仓后做一次）：

- About 里填 description + topics：`obsidian` `ai-agents` `claude-code` `codex` `deepseek-harness` `memory` `knowledge-management`
- 关掉 Wiki / Projects（用不上，空着难看）
- Issues 开着，模板不必加

## 5. PyPI（可选）

```bash
python -m pip install --upgrade build twine
python -m build
python -m twine upload dist/*
```

注意：本仓库**运行时零第三方依赖**，`[zstd]` / `[dev]` 都是可选 extra。上传前确认 wheel 里不含 `out/`、`vault/`、`.memloom/`（`.gitignore` 已排除，但 `MANIFEST` 改动过要复查 `python -m build` 的产物列表）。

## 6. 发版后

- [ ] 在 GitHub Release 上写更新说明（直接贴 `CHANGELOG.md` 那一节）
- [ ] 把 README 顶部加徽章（如果还没加）：

```markdown
[![tests](https://img.shields.io/badge/tests-47%20passing-brightgreen)](tests)
[![python](https://img.shields.io/badge/python-3.9%2B-blue)](pyproject.toml)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)
```

- [ ] 用 `pip install -e .` 在一个干净虚拟环境里装一次，跑 `memloom doctor`（这条能抓出「只在仓库目录里才跑得起来」的问题）
- [ ] 更新长期记忆里这个项目的状态页

## 附：CHANGELOG 模板

`CHANGELOG.md` 用最土的格式就够了，别引入工具：

```markdown
## v0.1.0 — 2026-11-13

- 三个适配器：DSH `.zstd`、Claude Code `.jsonl`、Codex rollout（beta）
- 规则抽取（路径 / 命令 / 错误 / 工具统计），不调用任何 LLM
- 项目聚类：cwd 分桶 + 共享文件并查集 + 超大桶再切分
- 三类主题：踩坑 / 代码 / 工具
- 增量解析：`<out>/.memloom/` 存 size + mtime_ns + 解析缓存
- `doctor` / `scan` / `build`（`--dry-run` / `--full` / `--since` / `--min-turns`）
```
