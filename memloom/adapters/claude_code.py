"""Claude Code session transcripts.

Format: ``~/.claude/projects/<path-slug>/<session-uuid>.jsonl`` — one JSON object per
line, mixing many ``type`` values. The ones that carry meaning::

    user        message.content = [{"type":"text"...}] | [{"type":"tool_result"...}]
                origin.kind == "human" for real prompts; isSidechain == true for sub-agents
    assistant   message.content = [{"type":"text"}|{"type":"thinking"}|{"type":"tool_use"}]
                message.model
    ai-title    aiTitle  (the human-readable session name Claude generates)
    summary     summary  (older transcripts)
    cost-state  totalCostUSD, modelUsage  <-- nobody else reads this; we do

Because a ``tool_result`` arrives as a ``user`` line, prompt detection must look at the
content blocks, not at ``type`` alone.
"""

from __future__ import annotations

import os
import re
from typing import Optional

from ..model import Session, ToolUse, Turn
from ..util import parse_iso
from .base import Adapter, clip, fallback_title, read_jsonl, squash, texts_of

__all__ = ["ClaudeCodeAdapter"]


class ClaudeCodeAdapter(Adapter):
    name = "claude-code"
    label = "Claude Code"
    suffixes = (".jsonl",)

    def default_roots(self) -> list:
        return [os.path.join(os.path.expanduser("~"), ".claude", "projects")]

    def match(self, path: str) -> bool:
        p = path.replace("/", os.sep)
        return (".claude" in p and "projects" in p) and p.endswith(".jsonl")

    def sniff(self, head: str) -> bool:
        sq = squash(head)
        if '"sessionid"' not in sq:
            return False
        return '"parentuuid"' in sq or '"issidechain"' in sq or '"permissionmode"' in sq or '"entrypoint"' in sq

    def load(self, path: str) -> Optional[Session]:
        sid = os.path.basename(path)[:-6] if path.endswith(".jsonl") else os.path.basename(path)
        title = ""
        cwd = None
        model = None
        cost = None
        git_branch = None
        version = None
        times = []
        turns = []
        cur = None
        by_call = {}
        skipped_sidechain = 0

        for d in read_jsonl(path):
            t = d.get("type")
            ts = parse_iso(d.get("timestamp"))
            if ts:
                times.append(ts)
            cwd = d.get("cwd") or cwd
            version = d.get("version") or version
            git_branch = d.get("gitBranch") or git_branch
            sid = d.get("sessionId") or sid

            if t == "ai-title":
                title = d.get("aiTitle") or title
                continue
            if t == "summary":
                title = title or d.get("summary") or ""
                continue
            if t == "cost-state":
                if isinstance(d.get("totalCostUSD"), (int, float)):
                    cost = float(d["totalCostUSD"])
                mu = d.get("modelUsage") or {}
                if isinstance(mu, dict) and mu and not model:
                    model = "claude:" + "/".join(sorted(mu)[:1])
                continue
            if t not in ("user", "assistant"):
                continue
            if d.get("isSidechain"):
                skipped_sidechain += 1
                continue

            msg = d.get("message") or {}
            blocks = msg.get("content")
            if msg.get("model"):
                model = model or f"claude/{msg['model']}"

            if t == "user":
                tool_results, user_text = _split_user_blocks(blocks)
                for tu_id, is_err, text in tool_results:
                    tu = by_call.get(tu_id)
                    if tu is None:
                        continue
                    tu.ok = not is_err
                    if is_err:
                        tu.error = clip(text, 300)
                if not user_text.strip():
                    continue  # pure tool_result line — not a prompt
                cur = Turn(index=len(turns) + 1, at=ts, prompt=clip(user_text, 4000))
                turns.append(cur)
            else:  # assistant
                if cur is None:
                    cur = Turn(index=len(turns) + 1, at=ts)
                    turns.append(cur)
                text = texts_of(blocks)
                if text.strip():
                    cur.reply = (cur.reply + "\n\n" + clip(text, 4000)).strip() if cur.reply else clip(text, 4000)
                for b in _iter_blocks(blocks):
                    if b.get("type") != "tool_use":
                        continue
                    name = b.get("name") or "?"
                    tu = ToolUse(name=name, summary=Adapter.tool_summary(name, b.get("input")))
                    cur.tools.append(tu)
                    if b.get("id"):
                        by_call[b["id"]] = tu
                if cur.at is None:
                    cur.at = ts

        if not any(x.prompt or x.reply or x.tools for x in turns):
            return None

        return Session(
            id=sid,
            source=os.path.abspath(path),
            adapter="claude-code",
            title=title or _fallback_title(turns),
            cwd=cwd,
            model=model,
            started_at=times[0] if times else None,
            ended_at=times[-1] if times else None,
            turns=turns,
            cost_usd=cost,
            meta={"version": version, "gitBranch": git_branch, "sidechain_skipped": skipped_sidechain},
        )


def _iter_blocks(blocks):
    if isinstance(blocks, dict):
        blocks = [blocks]
    if not isinstance(blocks, list):
        return
    for b in blocks:
        if isinstance(b, dict):
            yield b


def _split_user_blocks(blocks):
    """Return ([(tool_use_id, is_error, text)], prompt_text)."""
    results = []
    texts = []
    if isinstance(blocks, str):
        return results, blocks
    for b in _iter_blocks(blocks):
        btype = b.get("type")
        if btype == "tool_result":
            c = b.get("content")
            txt = texts_of(c) if not isinstance(c, str) else c
            if not txt:
                txt = str(b.get("output") or "")
            results.append((b.get("tool_use_id") or "", bool(b.get("is_error")), txt))
        elif btype in ("text", None):
            txt = b.get("text")
            if isinstance(txt, str) and txt:
                texts.append(txt)
    return results, "\n".join(texts)


def _fallback_title(turns) -> str:
    return fallback_title(turns)
