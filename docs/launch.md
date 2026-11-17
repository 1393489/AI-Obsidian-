# 发布文案（直接复制粘贴用）

> 这份文件是给**发布者**用的，不是给读者的。每段都按对应平台的调性写过：HN 要克制、Reddit 要具体、V2EX 要口语、掘金要技术。
> 链接统一用 `https://github.com/KrLito7/memloom`，别用短链、别带 UTM。

## 0. 顺序与节奏（比文案更重要）

| 顺序 | 平台 | 时机 | 说明 |
|---|---|---|---|
| 1 | GitHub **Release** | 现在 | 网页点两下，让仓库右侧出现 `v0.1.0` 徽章 |
| 2 | V2EX / 即刻 | 第一天 | 中文圈反馈最快，能立刻发现「哪里没说清」 |
| 3 | Reddit `r/ObsidianMD` | 隔一天 | 这里的人真的会跑你的代码，先修掉第一天的尴尬 |
| 4 | Show HN | 再隔一天 | 英文、工作日 8–10 点（美东）发，标题别花哨 |
| 5 | 掘金 / 少数派 | 之后 | 长文，可复用 HN 反馈里最强的那个问题当标题 |

三条纪律：**同一个链接一天只贴一处**；**别找朋友刷 star**（曲线一眼看得出）；**有人提 bug 当天回**（早期每条回复都算口碑）。

---

## 1. 一句话（各处复用）

**中文（一句话版）**
> 把你和 AI 写过的每一次对话，变成一本能翻、能跳、能搜的 Obsidian 库 —— 本地跑，不上传，不用 LLM。

**中文（痛点版，适合标题或开头）**
> AI 帮你解决的问题，全在 `.jsonl` 里躺着。下次遇到同一个报错，你只能重新问一遍。

**English**
> Turn your local AI coding sessions into a navigable Obsidian vault — offline, no LLM, no third-party dependencies.

---

## 2. GitHub Release 正文

见 [`release-notes-v0.1.0.md`](release-notes-v0.1.0.md)，整份复制。

操作：仓库主页 → 右侧 **Releases** → **Draft a new release** → 选 tag `v0.1.0` → 标题 `v0.1.0` → 粘贴正文 → Publish release。
（`v0.1.0` 这个 tag 已经存在，所以下拉框里能直接选到。）

---

## 3. V2EX（节点：分享创造 / 程序员）

**标题**
> 把 AI 编程对话变成 Obsidian 笔记库：一个零依赖、不用 LLM 的小工具

**正文**

```
和 AI 写代码写久了有个问题：那些解决问题的过程全都在本地档案里（Claude Code 的
.jsonl、DSH 的 zstd、Codex 的 rollout），但它们本质上是日志——打不开、搜不到、
下次遇到同一个报错只能重新问一遍。

所以我写了个东西，把它们读成一本 Obsidian 库：

  vault/
  ├── 00-总索引.md
  ├── 10-项目/      按工作目录 + 共享文件聚类出来的项目页
  ├── 20-会话/      一次会话一页：我问了什么、它答了什么、跑了什么命令、错在哪
  ├── 30-主题/      踩坑 / 代码 / 工具：同类问题跨会话归到一起
  ├── 90-原文归档/  原始档案的位置（不复制，只索引）
  └── 99-使用说明.md

页面之间全是 [[双链]]。点「工具-find」能看到所有用过 find 的会话，点「踩坑-xxx」
能看到这个错误跨会话的全部现场。

几个刻意的取舍：
- 零第三方依赖，纯标准库，Python 3.9+ 就能跑（起初是因为这台机器的 pip 时好时坏，
  索性什么都不装；后来发现这才是最好的卖点）
- 不用 LLM：路径、命令、错误、工具统计全靠规则抽。好处是同一批档案跑两次
  逐字节一致，能进 git 能 diff；坏处是主题名有时候很丑
- 只读档案目录，只往 --out 写
- 增量：第二次跑只重解析变过的档案（我这边 117 个档案 289 MB：14.1s → 3.3s → 0.6s）

https://github.com/KrLito7/memloom

自测 47 个用例，CI 跑 3.9/3.12/3.13 × Win/Linux。Codex 的适配器目前还是 beta，
只在我造的样本上验过（这台机器没装 Codex）。

想听两件事：你用的是什么 AI 客户端（Cursor？Aider？Copilot？）—— 适配器我照着加；
以及你觉得哪些页压根不会点开（我可以直接不生成）。
```

---

## 4. Reddit `r/ObsidianMD`

**Title**
> I turned my Claude Code / Codex session logs into an Obsidian vault — no LLM, no cloud, no dependencies

**Body**

```
I keep solving the same problems twice because the solution is buried in a
`.jsonl` log somewhere. So I wrote a small tool that reads those archives and
turns them into an actual vault:

    00-总索引        project map + topic index + timeline
    10-项目           one page per project (clustered by cwd + shared files)
    20-会话           one page per session: prompts, replies, commands, errors
    30-主题           cross-session topics: pitfalls / code / tools
    90-原文归档        pointers to the raw archives (nothing is copied)
    99-使用说明        how the vault was generated

Everything is `[[wikilinked]]`, so clicking `工具-find` in a session jumps to
every session that ran find. Clicking a pitfall jumps to every place that error
showed up.

Two deliberate constraints:

**No LLM.** Paths, commands, error fingerprints, tool usage and titles are all
extracted by rules. Same archives in → byte-identical vault out, so you can
commit it and diff it. The tradeoff is that topic names are occasionally
clunky ("踩坑-grep search failed (exit 2)") — LLM naming is planned as an
*optional* flag in v0.2, never a requirement.

**Nothing but the standard library.** Python 3.9+, zero runtime deps.

Incremental by default: on my 117 archives / 289 MB it's 14.1s cold, 3.3s on a
rerun, 0.6s after that, and a rerun writes 0 files (so rebuilding doesn't
reset whatever you're reading).

Repo: https://github.com/KrLito7/memloom  (MIT)

What I'd genuinely like to know: which AI client do you use? Adapters for
Cursor / Aider / Copilot would each be ~150 lines and I'd rather write the one
people actually need than guess. Also happy to hear which pages you'd never
open — deleting output is as useful as adding it.
```

---

## 5. Show HN

**Title**
> Show HN: Memloom – AI coding session logs into a navigable Obsidian vault

**Text**（HN 帖可以不填 URL 时用 text 版；填了 URL 就留空）

```
Every AI coding session I've had in the last year is sitting in
~/.claude/projects, ~/.codex/sessions and ~/.dsh/sessions as line-delimited
JSON and zstd frames. They contain every problem I already solved. They are
also unreadable, and I keep re-solving the same problems.

Memloom reads them and emits an Obsidian vault: one page per session, per
project (clustered by working directory and shared files), and per topic
(pitfalls, code areas, tools — topics are cross-session). Pages are
wikilinked, so a session page links to the topics it touched and back to its
project.

Design choices that people usually push back on:

- No LLM anywhere. Extraction is rule-based (paths, commands, error
  fingerprints, tool call counts). Deterministic output: same input, same
  bytes. Topic names are therefore mechanical — "pitfall: grep search failed
  (exit 2)" — which I consider acceptable; auto-naming is an opt-in flag in
  the next version.
- Zero third-party runtime dependencies (stdlib only, Python 3.9+). zstd
  decoding falls back through pyzstd → stdlib → node → the zstd CLI, so a
  machine with a broken pip still works.
- Read-only on the archives; the only writes go to --out.
- Incremental: 117 archives / 289 MB takes 14.1s cold, 3.3s on rerun, 0.6s
  after that, and a rerun writes zero files.

Adapters today: Claude Code, Codex (beta — synthetic fixtures only, no Codex
on this machine to test against), and DSH. Adding one is ~150 lines.

https://github.com/KrLito7/memloom

Curious whether the "no LLM" call is right. For a personal archive I think
deterministic beats clever, but I can see the argument that ugly topic names
defeat the purpose of the vault in the first place.
```

---

## 6. 掘金 / 少数派（长文骨架）

标题候选：

- 《我把一年的 AI 编程对话做成了 Obsidian 库，顺便踩了 zstd 的坑》
- 《不用 LLM 也能把聊天记录变成笔记库：规则抽取的取舍》

结构：**痛点 → 我先试过的错做法 → 档案格式长什么样 → 规则抽取怎么做 → 聚类怎么分项目/主题 → 增量的坑（mtime 会骗你）→ 实测数字 → 不做什么（LLM/云）**。
每节配一张真实截图或代码块，别配插画。技术读者只信真实输出。

---

## 7. 即刻 / 微博 / 朋友圈（短）

```
AI 帮你解决的问题，都躺在 .jsonl 里，下次遇到同一个报错还是得重新问一遍。
我写了个小工具把它们读成一本 Obsidian 库：一次会话一页、跨会话的踩坑归成一页，
全是双链、能点。本地跑、不上传、不用 LLM、零依赖。
https://github.com/KrLito7/memloom
```

---

## 8. 回复模板（提前想好，别临场写软话）

**「为什么不用 LLM 总结？名字好丑。」**
> 故意的。规则抽的副作用是名字丑，好处是同输入同输出——可以进 git、可以 diff、不用为了一次整理付钱也不用担心隐私。LLM 命名我做成了可选开关（`--enrich`，v0.2），不装也能用。

**「支持 Cursor / Aider / Copilot 吗？」**
> 还没。加一个适配器大概 150 行（读文件 → 产出统一的会话模型），你把档案目录结构告诉我就行，或者直接开个 issue 贴一段脱敏样本。

**「和 Obsidian 的 Local REST API / Smart Connections 有什么区别？」**
> 那些是「已经进库之后」的工具；我做的是把「压根不是库」的东西变成库。可以叠着用。

**「会不会把我的对话传上去？」**
> 不会，代码里没有任何网络请求。可以 `grep -r "http" memloom/` 自己看——只有 URL 识别用的正则。

**「为什么不做成 Obsidian 插件？」**
> 插件得在 Obsidian 里跑 JS，zstd 和几十 MB 的 JSONL 解析会很别扭；而且我希望它在你没装 Obsidian 时也能用（`--dry-run` 只算不写）。以后可以包一层。

---

## 9. 发完之后

1. **Traffic 面板**（仓库 Insights → Traffic）每天看一眼：`referrers` 会告诉你哪个渠道真带来了人，比 star 数诚实。
2. 有人开 issue 就当天回；前 10 个 issue 决定别人敢不敢用。
3. 有人问功能 → 先问「你现在怎么解决的」，别直接写代码。
4. 一轮发完两周内没有起色，就是**定位**问题不是文案问题：要么受众不在，要么痛点不够痛。那时候该改的是 README 第一屏，不是再发一次。
