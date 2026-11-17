# memloom v0.1.0

把本地的 AI 编程会话，织成一本能翻、能链、能搜索的 Obsidian 记忆库。
Turn your AI coding sessions into a navigable Obsidian memory vault — local, offline, no LLM required.

---

## 它做什么

读 `~/.dsh/sessions`、`~/.claude/projects`、`~/.codex/sessions` 里的原始档案（行分隔 JSON、拼接的 zstd 帧），生成一本 Obsidian 库：

```
vault/
├── 00-总索引.md          项目地图 + 主题分类 + 时间线
├── 10-项目/              按工作目录 + 共享文件聚类出的项目页
├── 20-会话/              一次会话一页：问了什么、答了什么、跑了什么、错在哪
├── 30-主题/              踩坑 / 代码 / 工具 —— 同类问题跨会话归到一起
├── 90-原文归档/          原始档案的位置（不复制、只索引）
└── 99-使用说明.md        这本库怎么生成的、哪些字是机器写的
```

页面之间全部是 `[[双链]]`：从一页会话可以直接跳到它所属的项目、它踩过的坑、它碰过的文件。

## 安装

```bash
git clone https://github.com/KrLito7/memloom.git
cd memloom
python -m memloom doctor      # 体检：档案目录在不在、zstd 后端走的哪条路
python -m memloom build --out vault
```

然后用 Obsidian「打开文件夹作为仓库」指到 `vault/`。

不需要 `pip install`：零第三方运行时依赖，纯标准库，Python 3.9+ 即可。想装成命令再加 `pip install -e .`（之后直接 `memloom build`）。

## 这个版本有什么

- **三个适配器**：Claude Code（`.jsonl`）、DSH（拼接 zstd 帧，`session.v4.jsonl.zstd`）、Codex（rollout JSONL，**beta**）
- **规则抽取，不用 LLM**：工作目录、命令、错误指纹、工具调用统计、会话标题全部由规则得到。同一批档案跑两次，输出逐字节一致 —— 可以进 git、可以 diff
- **聚类**：cwd 归一化分桶 → 文件共现 union-find → 关键词相似度，过大的簇自动切分
- **增量**：`<out>/.memloom/state.json` 记录每条档案的 size + mtime_ns，只重解析变过的档案；内容没变的页面零写入
- **只读档案**：不在档案目录里写任何东西，不上传任何内容，唯一写的地方是 `--out`
- **47 个单元测试**，CI 跑 Python 3.9 / 3.12 / 3.13 × Ubuntu / Windows

## 实测（作者机器，2026-11-14）

| | |
|---|---|
| 输入 | 117 个档案 / 289 MB |
| 输出 | 117 会话 / 9 项目 / 60 主题 / 189 页 |
| 第一次（全解析） | 14.1 s |
| 第二次（档案没动） | 3.26 s |
| 第三次 | 0.64 s |

你自己的档案数量和耗时会不一样 —— 档案只会越攒越多。

## 已知限制

- **Codex 适配器是 beta**：只有合成 fixture 验证过，作者机器上没装 Codex，没有真实样本
- **没有发布到 PyPI**：请用源码跑（`python -m memloom`）或 `pip install -e .`
- **主题名是机械的**：`踩坑-grep search failed (exit N)` 这种。LLM 起名计划放在 v0.2，作为**可选开关**，不是前置条件
- 没有 GUI、不做双向同步（改库不会回写档案，也不打算做）

## 或许你也想要

- 学习一本库的结构：看 [`examples/sample-vault/`](https://github.com/KrLito7/memloom/tree/main/examples/sample-vault)（五页真实输出）
- 只有五分钟：`memloom build --dry-run` 只算不写；`memloom scan` 只报档案数
- 换机器/换客户端：适配器约 150 行一个，见 [`docs/adapters.md`](https://github.com/KrLito7/memloom/blob/main/docs/adapters.md)

完整文档在 [README](https://github.com/KrLito7/memloom#readme)。MIT 许可。

有任何用不上的地方直接开 issue 说「这页我从来不会点」——删除输出和增加输出一样有用。
