"""OpenAI Codex CLI rollouts.

Format: ``~/.codex/sessions/YYYY/MM/DD/rollout-<ts>-<uuid>.jsonl``, each line
``{"timestamp": ..., "type": ..., "payload": {...}}`` where ``type`` is::

    session_meta     payload = {id, timestamp, cwd, originator, cli_version}
    turn_context     payload = {cwd, model, ...}
    response_item    payload = {type: "message"|"function_call"|"function_call_output", ...}
    event_msg        payload = {type: "user_message"|"agent_message"|"token_count", ...}

.. warning::
   Written from the documented rollout schema and fixtures, not yet validated against a
   live Codex install on this machine (no ``~/.codex`` present). Treated as beta: if your
   files look different, open an issue with one line of the file and we add the shape.
"""

from __future__ import annotations

import os
import re
from typing import Optional

from ..model import Session, ToolUse, Turn
from ..util import parse_iso
from .base import Adapter, clip, read_jsonl, squash, texts_of

__all__ = ["CodexAdapter"]


class CodexAdapter(Adapter):
    name = "codex"
    label = "Codex CLI"
    suffixes = (".jsonl",)

    def default_roots(self) -> list:
        return [os.path.join(os.path.expanduser("~"), ".codex", "sessions")]

    def match(self, path: str) -> bool:
        p = path.replace("/", os.sep)
        return (".codex" in p and "sessions" in p) and p.endswith(".jsonl") and os.path.basename(p).startswith("rollout-")

    def sniff(self, head: str) -> bool:
        sq = squash(head)
        return '"session_meta"' in sq and '"payload"' in sq

    def load(self, path: str) -> Optional[Session]:
        sid = os.path.basename(path)[:-6]
        title = ""
        cwd = None
        model = None
        times = []
        turns = []
        cur = None
        by_call = {}
        meta = {}

        for d in read_jsonl(path):
            ts = parse_iso(d.get("timestamp"))
            if ts:
                times.append(ts)
            t = d.get("type")
            p = d.get("payload") or {}

            if t == "session_meta":
                sid = p.get("id") or sid
                cwd = p.get("cwd") or cwd
                meta = {"originator": p.get("originator"), "cli_version": p.get("cli_version")}
                continue
            if t == "turn_context":
                cwd = p.get("cwd") or cwd
                model = p.get("model") or model
                continue

            if t == "event_msg":
                et = p.get("type")
                if et == "user_message":
                    text = p.get("message") or ""
                    if text.strip():
                        cur = Turn(index=len(turns) + 1, at=ts, prompt=clip(text, 4000))
                        turns.append(cur)
                elif et == "agent_message":
                    text = p.get("message") or ""
                    if text.strip() and cur is not None:
                        cur.reply = (cur.reply + "\n\n" + clip(text, 4000)).strip() if cur.reply else clip(text, 4000)
                continue

            if t != "response_item":
                continue
            pt = p.get("type")
            if pt == "message":
                role = p.get("role")
                text = texts_of(p.get("content"))
                if not text.strip():
                    continue
                if role == "user":
                    if cur is None or cur.prompt:
                        cur = Turn(index=len(turns) + 1, at=ts)
                        turns.append(cur)
                    cur.prompt = clip(text, 4000)
                elif cur is not None:
                    cur.reply = (cur.reply + "\n\n" + clip(text, 4000)).strip() if cur.reply else clip(text, 4000)
            elif pt == "function_call":
                if cur is None:
                    cur = Turn(index=len(turns) + 1, at=ts)
                    turns.append(cur)
                name = p.get("name") or "?"
                tu = ToolUse(name=name, summary=Adapter.tool_summary(name, p.get("arguments")))
                cur.tools.append(tu)
                if p.get("call_id"):
                    by_call[p["call_id"]] = tu
            elif pt == "function_call_output":
                tu = by_call.get(p.get("call_id") or "")
                if tu is None:
                    continue
                out = p.get("output")
                txt = out if isinstance(out, str) else texts_of(out)
                tu.ok = True
                if txt and re.search(r"\b(error|failed|exit code: [1-9]|Traceback)\b", txt, re.I):
                    tu.ok = False
                    tu.error = clip(txt, 300)

        if not any(x.prompt or x.reply or x.tools for x in turns):
            return None

        return Session(
            id=sid,
            source=os.path.abspath(path),
            adapter="codex",
            title=title or _fallback_title(turns),
            cwd=cwd,
            model=model,
            started_at=times[0] if times else None,
            ended_at=times[-1] if times else None,
            turns=turns,
            meta=meta,
        )


def _fallback_title(turns) -> str:
    for t in turns:
        if t.prompt:
            return clip(re.sub(r"\s+", " ", t.prompt).strip(), 40)
    return "(无标题)"
